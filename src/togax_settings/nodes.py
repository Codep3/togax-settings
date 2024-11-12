from schema import And, Schema, SchemaError
from toga.sources import Source


def _get_validator(schema):
    def schema_validator(value):
        if schema == float:
            try:
                value = float(value)
            except ValueError as e:
                return f"Not valid input: {e}"
        if not schema:
            return None
        try:
            Schema(schema).validate(value)
            return None
        except SchemaError as e:
            return f"Not valid input: {e}"

    return schema_validator


class BaseNode(Source):
    def __init__(
        self,
        key,
        value,
        parent=None,
        keyschema=None,
        schema=None,
        path=(),
    ):
        super().__init__()
        self.key = key
        self.value = value
        self.parent = parent
        self.children = []
        self.keyschema = keyschema
        self.key_validator = _get_validator(self.keyschema)
        self.schema = schema
        self.validator = _get_validator(self.schema)
        self.path = self._construct_path()

    def _construct_path(self):
        if self.parent is None:
            return ()
        parent_path = self.parent.path
        if isinstance(self.parent.schema, dict):
            for schema_key, schema_value in self.parent.schema.items():
                if schema_value == self.schema:
                    return parent_path + (schema_key,)
            else:
                return parent_path + (self.parent.key,)
        elif isinstance(self.parent.schema, list):
            return parent_path + (0,)
        return parent_path

    def update_value(self, new_value):
        if self.validator:
            error = self.validator(new_value)
            if error:
                raise ValueError(error)

        self.value = new_value
        if self.parent:
            self.parent.value[self.key] = new_value
        self.notify("change_node", item=self)

    def __len__(self):
        return len(self.children)

    def __getitem__(self, index):
        return self.children[index]

    def can_have_children(self):
        return bool(self.children)

    @property
    def name(self):
        return self.key

    def to_dict(self):
        return self.value


class DictNode(BaseNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._add_children()

    def _add_children(self):
        for child_key, child_value in self.value.items():
            child_keyschema, child_schema = self._get_child_schemas(child_key)
            child = create_node(
                child_key,
                child_value,
                parent=self,
                keyschema=child_keyschema,
                schema=child_schema,
                path=self.path,
            )
            self.children.append(child)

    def _get_child_schemas(self, key):
        child_keyschema = None
        child_schema = None

        if self.schema is None:
            return None, None

        if isinstance(self.schema, dict):
            if key in self.schema:
                child_schema = self.schema[key]
            else:
                for k, v in self.schema.items():
                    if isinstance(k, type):
                        try:
                            Schema(k).validate(key)
                            child_schema = v
                            child_keyschema = k
                            break
                        except SchemaError:
                            pass
                    elif isinstance(k, (Schema, And)):
                        try:
                            k.validate(key)
                            child_schema = v
                            child_keyschema = k
                            break
                        except SchemaError:
                            pass
            if child_schema is None:
                child_schema = self.schema.get(
                    key, self.schema.get(str, self.schema.get(int, None))
                )

        return child_keyschema, child_schema

    def to_dict(self):
        return {child.key: child.to_dict() for child in self.children}


class ListNode(BaseNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._add_children()

    def _add_children(self):
        for index, item in enumerate(self.value):
            child_schema = self._get_list_item_schema()
            child = create_node(
                index, item, parent=self, schema=child_schema, path=self.path
            )
            self.children.append(child)

    def _get_list_item_schema(self):
        if isinstance(self.schema, list):
            return self.schema[0] if self.schema else None
        return None

    def add_list_item(self, value):
        self.value.append(value)
        child_schema = self._get_list_item_schema()
        child = create_node(
            len(self.children), value, parent=self, schema=child_schema, path=self.path
        )
        self.children.append(child)
        self.notify("add_node", parent=self, child=child, key=child.key)

    def to_dict(self):
        return [child.to_dict() for child in self.children]


class ValueNode(BaseNode):
    def _add_children(self):
        pass  # Value nodes don't have children


def create_node(key, value, **kwargs):
    if isinstance(value, dict):
        return DictNode(key, value, **kwargs)
    elif isinstance(value, list):
        return ListNode(key, value, **kwargs)
    else:
        return ValueNode(key, value, **kwargs)
