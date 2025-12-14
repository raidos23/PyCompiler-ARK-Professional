def log_info(self, message: str) -> None:
    self.log(f"[INFO] {message}")


def log_warn(self, message: str) -> None:
    self.log(f"[WARN] {message}")


def log_error(self, message: str) -> None:
    self.log(f"[ERROR] {message}")
