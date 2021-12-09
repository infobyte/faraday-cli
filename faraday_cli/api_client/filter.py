class FaradayFilter:
    def __init__(self):
        self.__status_required = []
        self.__status_not_required = []
        self.__severities_required = []
        self.__severities_ignored = []
        self.__confirmed = False

    def require_severity(self, severity: str) -> None:
        if severity not in self.__severities_required:
            self.__severities_required.append(severity)

    def ignore_severity(self, severity: str) -> None:
        if severity not in self.__severities_ignored:
            self.__severities_ignored.append(severity)

    def filter_confirmed(self) -> None:
        self.__confirmed = True

    def get_filter(self) -> dict:
        filter_data = []

        if self.__severities_required:
            if len(self.__severities_required) > 1:
                filter_data.append(
                    {
                        "or": [
                            {"name": "severity", "op": "eq", "val": value}
                            for value in self.__severities_required
                        ]
                    }
                )
            else:
                filter_data.append(
                    {
                        "name": "severity",
                        "op": "eq",
                        "val": self.__severities_required[0],
                    }
                )

        if self.__severities_ignored:
            if len(self.__severities_ignored) > 1:
                filter_data.append(
                    {
                        "and": [
                            {"name": "severity", "op": "neq", "val": value}
                            for value in self.__severities_ignored
                        ]
                    }
                )
            else:
                filter_data.append(
                    {
                        "name": "severity",
                        "op": "neq",
                        "val": self.__severities_ignored[0],
                    }
                )
        if self.__confirmed:
            if filter_data:
                filter_data.append(
                    {"and": [{"name": "confirmed", "op": "eq", "val": "true"}]}
                )
            else:
                filter_data.append(
                    {"name": "confirmed", "op": "eq", "val": "true"}
                )
        return {"filters": filter_data}
