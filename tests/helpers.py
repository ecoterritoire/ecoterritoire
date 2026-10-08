class CursorContext:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, *_):
        return False


class DatabaseContext:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return CursorContext(self.cursor_obj)

    def commit(self):
        self.committed = True

    def close(self):
        pass
