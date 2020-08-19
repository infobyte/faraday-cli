'''
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

'''
from tempfile import NamedTemporaryFile

import os
import sys
import json
import pytest
from flask.testing import FlaskClient
from flask_principal import identity_changed, Identity
from sqlalchemy import event

sys.path.append(os.path.abspath(os.getcwd()))
from faraday.server.app import create_app
from faraday.server.models import db


TEST_BASE = os.path.abspath(os.path.dirname(__file__))
TEST_DATA = os.path.join(TEST_BASE, 'data')

TEMPORATY_SQLITE = NamedTemporaryFile()


class CustomClient(FlaskClient):

    def open(self, *args, **kwargs):
        if kwargs.pop('use_json_data', True) and 'data' in kwargs:
            # JSON-encode data by default
            kwargs['data'] = json.dumps(kwargs['data'])
            kwargs['headers'] = kwargs.get('headers', []) + [
                ('Content-Type', 'application/json'),
            ]

        # Reset queries to make the log_queries_count
        from flask import _app_ctx_stack
        _app_ctx_stack.top.sqlalchemy_queries = []

        ret = super(CustomClient, self).open(*args, **kwargs)
        return ret

    @property
    def cookies(self):
        return self.cookie_jar


def pytest_addoption(parser):
    # currently for tests using sqlite and memory have problem while using transactions
    # we need to review sqlite configuraitons for persistence using PRAGMA.
    parser.addoption('--connection-string', default='sqlite:////{0}'.format(TEMPORATY_SQLITE.name),
                     help="Database connection string. Defaults to in-memory "
                     "sqlite if not specified:")


@pytest.fixture(scope='session')
def app(request):
    app = create_app(db_connection_string=request.config.getoption(
        '--connection-string'), testing=True)
    app.test_client_class = CustomClient

    # Establish an application context before running the tests.
    ctx = app.app_context()
    ctx.push()

    def teardown():
        TEMPORATY_SQLITE.close()
        ctx.pop()

    request.addfinalizer(teardown)
    return app


@pytest.fixture(scope='session')
def database(app, request):
    """Session-wide test database."""

    def teardown():
        try:
            db.engine.execute('DROP TABLE vulnerability CASCADE')
        except Exception:
            pass
        try:
            db.engine.execute('DROP TABLE vulnerability_template CASCADE')
        except Exception:
            pass
        db.drop_all()

    # Disable check_vulnerability_host_service_source_code constraint because
    # it doesn't work in sqlite
    vuln_constraints = db.metadata.tables['vulnerability'].constraints
    vuln_constraints.remove(next(
        constraint for constraint in vuln_constraints
        if constraint.name == 'check_vulnerability_host_service_source_code'))

    db.app = app
    db.create_all()

    request.addfinalizer(teardown)
    return db


@pytest.fixture(scope='function')
def fake_session(database, request):
    connection = database.engine.connect()
    transaction = connection.begin()

    options = {"bind": connection, 'binds': {}}
    session = db.create_scoped_session(options=options)

    database.session = session
    db.session = session

    def teardown():
        # rollback - everything that happened with the
        # Session above (including calls to commit())
        # is rolled back.
        # be careful with this!!!!!
        transaction.rollback()
        connection.close()
        session.remove()

    request.addfinalizer(teardown)
    return session


@pytest.fixture(scope='function')
def session(database, request):
    """Use this fixture if the function being tested does a session
    rollback.

    See http://docs.sqlalchemy.org/en/latest/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites
    for further information
    """
    connection = database.engine.connect()
    transaction = connection.begin()

    options = {"bind": connection, 'binds': {}}
    session = db.create_scoped_session(options=options)

    # start the session in a SAVEPOINT...
    session.begin_nested()

    # then each time that SAVEPOINT ends, reopen it
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:

            # ensure that state is expired the way
            # session.commit() at the top level normally does
            # (optional step)
            session.expire_all()

            session.begin_nested()

    database.session = session
    db.session = session

    def teardown():
        # rollback - everything that happened with the
        # Session above (including calls to commit())
        # is rolled back.
        # be careful with this!!!!!
        transaction.rollback()
        connection.close()
        session.remove()

    request.addfinalizer(teardown)
    return session


@pytest.fixture
def test_client(app):

    # flask.g is persisted in requests, and the werkzeug
    # CSRF checker could fail if we don't do this
    from flask import g
    try:
        del g.csrf_token
    except:
        pass

    return app.test_client()


@pytest.fixture(scope='function')
def token(app, session, test_client):
    def create_user(app, session, username, email, password, **kwargs):
        user = app.user_datastore.create_user(username=username,
                                              email=email,
                                              password=password,
                                              **kwargs)
        session.add(user)
        session.commit()
        return user

    user = create_user(app, session, 'test', 'user@test.com', 'password',
                       is_ldap=False)

    with test_client.session_transaction() as sess:
        # Without this line the test breaks. Taken from
        # http://pythonhosted.org/Flask-Testing/#testing-with-sqlalchemy
        assert user.id is not None
        db.session.add(user)
        sess['_user_id'] = user.id  # TODO use public flask_login functions
        identity_changed.send(test_client.application,
                              identity=Identity(user.id))

    token_response = test_client.get("/v2/token/")
    token = token_response.json
    test_client.get("/logout", json=dict())
    token_response = test_client.get("/v2/token/")
    assert token_response.status_code == 401
    return token


@pytest.fixture()
def ok_configuration_file(token):
    with NamedTemporaryFile() as file:
        # TODO Write data to file
        file.write(f"TOKEN = {token}".encode())
        file.seek(0)
        yield file



@pytest.fixture(autouse=True)
def skip_by_sql_dialect(app, request):
    dialect = db.session.bind.dialect.name
    if request.node.get_closest_marker('skip_sql_dialect'):
        if request.node.get_closest_marker('skip_sql_dialect').args[0] == dialect:
            pytest.skip('Skipped dialect is {}'.format(dialect))

