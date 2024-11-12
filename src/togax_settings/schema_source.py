import yaml
from schema import Schema, SchemaError

from .nodes import DictNode, create_node


class SchemaNode(DictNode):
    def __init__(
        self,
        key,
        value,
        parent=None,
        keyschema=None,
        schema=None,
        path=(),
        defaults_dict={},
    ):
        if parent is None:
            self.defaults = defaults_dict
        super().__init__(key, value, parent, keyschema, schema, path)

    def on_add(self, node, default_value):
        if isinstance(node.value, list):
            return node.add_list_item(default_value)
        node.value = default_value
        for key, value in default_value.items():
            child_keyschema, child_schema = node._get_child_schemas(key)
            child = create_node(
                key,
                value,
                parent=node,
                keyschema=child_keyschema,
                schema=child_schema,
                path=self.path,
            )
            node.children.append(child)
        node.notify("add_node", child=child)

    def on_remove(self, node):
        if node.parent:
            del node.parent.value[node.key]
            node.parent.children.remove(node)
        node.notify("remove_node", key=node.key)


class SchemaDataSource(SchemaNode):
    def __init__(
        self,
        settings_name,
        data,
        schema,
        yaml_file,
        defaults_dict={},
        example_yaml=None,
    ):
        self.schema = schema
        self.yaml_file = yaml_file
        self.example_yaml = example_yaml
        super().__init__(
            settings_name, data, schema=schema, defaults_dict=defaults_dict
        )

    @staticmethod
    def validate_data(data, schema):
        try:
            Schema(schema).validate(data)
        except SchemaError as e:
            raise ValueError(f"Data does not match schema: {e}")

    @classmethod
    def from_yaml(
        cls, settings_name, yaml_file, schema, defaults_dict={}, example_yaml=None
    ):
        """Create a SchemaDataSource from a YAML file.

        If the yaml_file doesn't exist and example_yaml is provided, the example
        will be copied to yaml_file after validation.
        """
        import os
        import shutil

        if not os.path.exists(yaml_file):
            if example_yaml is None:
                raise FileNotFoundError(
                    f"Settings file {yaml_file} not found and no example file provided"
                )

            if not os.path.exists(example_yaml):
                raise FileNotFoundError(f"Example file {example_yaml} not found")

            # Validate example file first
            with open(example_yaml) as file:
                example_data = yaml.safe_load(file)
            cls.validate_data(example_data, schema)

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(yaml_file), exist_ok=True)

            # Copy validated example file
            shutil.copy2(example_yaml, yaml_file)
            data = example_data
        else:
            try:
                with open(yaml_file) as file:
                    data = yaml.safe_load(file)
                # Validate existing file
                cls.validate_data(data, schema)
            except (yaml.YAMLError, ValueError) as e:
                if example_yaml is None:
                    raise ValueError(
                        f"Invalid YAML file {yaml_file} and no example file provided: {e}"
                    )

                # Backup the invalid file
                backup_file = f"{yaml_file}.backup"
                import shutil

                shutil.copy2(yaml_file, backup_file)

                # Load and validate example file
                with open(example_yaml) as file:
                    example_data = yaml.safe_load(file)
                cls.validate_data(example_data, schema)

                # Copy validated example file
                shutil.copy2(example_yaml, yaml_file)
                data = example_data
                print(
                    f"Invalid YAML file backed up to {backup_file} and replaced with example file"
                )

        return cls(
            settings_name,
            data,
            schema,
            yaml_file,
            defaults_dict=defaults_dict,
            example_yaml=example_yaml,
        )

    def save_to_yaml(self):
        data = self.to_dict()
        try:
            self.validate_data(data, self.schema)
            with open(self.yaml_file, "w") as file:
                yaml.dump(data, file)
        except ValueError as e:
            print(f"Error saving file: {e}")

    def on_change(self):
        self.save_to_yaml()

    def on_remove(self, node):
        super().on_remove(node)
        self.on_change()

    def on_add(self, node, default_value):
        super().on_add(node, default_value)
        self.on_change()
