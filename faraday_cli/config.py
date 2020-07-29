import os
import yaml
DEFAULT_CONFIG_FILE = "~/.faraday-cli.yml"

class Config:

    def __init__(self):
        self.config_file = os.path.expanduser(DEFAULT_CONFIG_FILE)
        self.faraday_url = None
        self.session = None
        self.ssl_verify = True
        self.workspace = None

    def load(self):
        with open(self.config_file) as f:
            config_data = yaml.load(f, Loader=yaml.FullLoader)
        self.faraday_url = config_data['auth']['faraday_url']
        self.session = config_data['auth']['session']
        self.ssl_verify = config_data['auth']['ssl_verify']
        self.workspace = config_data['workbench']['workspace']

    def save(self):
        config_data = {'auth': {'faraday_url': self.faraday_url,
                                'session': self.session,
                                'ssl_verify': self.ssl_verify},
                       'workbench': {'workspace': self.workspace}
                       }
        with open(self.config_file, 'w') as f:
            yaml.dump(config_data, f)


active_config = Config()
