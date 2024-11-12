import os

import toga

# Dialogs are now called directly on the window
from schema import Schema, SchemaError  # , And, Optional

# from schema_source import CustomDataSource
from toga.constants import COLUMN, ROW
from toga.platform import get_platform_factory

# from toga.sources import Source
from toga.style import Pack

TOGA_PLATFORM = get_platform_factory().__name__


class SchemaNodeWidget(toga.Box):
    def __init__(self, root_node, node, style=Pack(direction=ROW, padding=(0, 5))):
        super().__init__(style=style)
        self.node = node
        self.key_widget = None
        self.value_widget = None
        self.root_node = root_node

        self._create_key_widget()

        if not isinstance(self.node.value, (dict, list)):
            self._create_value_widget()

        self._create_remove_button()
        self._create_add_button()

    def _create_remove_button(self):
        if self._can_remove():
            remove_button = toga.Button(
                "X", on_press=self._remove_node, style=Pack(padding_left=5)
            )
            self.add(remove_button)

    def _create_add_button(self):
        if self.node.path not in self.root_node.defaults:
            return
        if isinstance(self.node.value, dict):
            add_button = toga.Button(
                "+", on_press=self._add_default, style=Pack(padding_left=5)
            )
            self.add(add_button)
        elif isinstance(self.node.value, list):
            add_button = toga.Button(
                "+", on_press=self._add_default_list, style=Pack(padding_left=5)
            )
            self.add(add_button)

    def _can_remove(self):
        # Check if the node and its children can be removed and still validate
        if self.node.parent is None:
            return False

        # If parent is a dict, ensure we're not trying to remove the last required key
        if isinstance(self.node.parent.value, dict):
            # Create a temporary dict without this key
            temp_dict = self.node.parent.to_dict()
            del temp_dict[self.node.key]

            try:
                # Validate against parent's schema
                Schema(self.node.parent.schema).validate(temp_dict)
                return True
            except SchemaError:
                # If validation fails, this key is required
                return False

        # For non-dict parents (like lists), always allow removal
        return True

    def _can_add(self):
        return self.node.path in self.root_node.defaults and isinstance(
            self.node.value, (dict, list)
        )

    def _remove_node(self, widget):
        if self._can_remove():
            self.root_node.on_remove(self.node)
        else:
            print("Cannot remove this item - it is required by the schema")

    def _add_default(self, widget):
        default_value = self.root_node.defaults[self.node.path]
        self.root_node.on_add(self.node, default_value)

    def _create_key_widget(self):
        if self.node.keyschema:
            self.key_widget = toga.TextInput(
                validators=[self.node.key_validator],
                value=self.node.key,
                style=Pack(flex=1, padding_right=5),
            )
            self.key_widget.on_change = lambda widget: self.on_value_change(
                widget, is_key=True
            )
        else:
            self.key_widget = toga.Label(
                self.node.key, style=Pack(flex=1, padding_right=5)
            )
        self.add(self.key_widget)

    def _create_value_widget(self):
        value_type = self._get_value_type()
        if value_type == int and TOGA_PLATFORM != "toga_textual.factory":
            self.value_widget = toga.NumberInput(
                value=self.node.value, style=Pack(flex=1)
            )
            self.value_widget.on_change = lambda widget: self.on_value_change(
                widget, is_key=False
            )
        else:
            self.value_widget = toga.TextInput(
                validators=[self.node.validator],
                value=str(self.node.value),
                style=Pack(flex=1),
            )
            self.value_widget.on_change = lambda widget: self.on_value_change(
                widget, is_key=False
            )

        self.add(self.value_widget)

    def _get_value_type(self):
        if self.node.schema:
            if isinstance(self.node.schema, dict):
                return self.node.schema.get(self.node.key, str)
            else:
                return self.node.schema
        return type(self.node.value)

    def on_value_change(self, widget, is_key):
        new_value = widget.value

        if is_key:
            current_value = self.node.key
            validator = self.node.key_validator
        else:
            current_value = self.node.value
            validator = self.node.validator

        # Convert to int if the original value was an int (only for non-key values)
        if not is_key and isinstance(current_value, int):
            try:
                new_value = int(new_value)
            except ValueError:
                print(f"Invalid integer value: {new_value}")
                return

        # Convert to float if the original value was a float (only for non-key values)
        if not is_key and isinstance(current_value, float):
            try:
                new_value = float(new_value)
            except ValueError:
                print(f"Invalid float value: {new_value}")
                return

        # Check if the value has actually changed
        if new_value == current_value:
            return
        if validator:
            error = validator(new_value)
            if error:
                # Show error message to user
                print(f"Validation error: {error}")
                return

        # Update the node's key or value
        if is_key:
            old_key = self.node.key
            self.node.key = new_value
            if self.node.parent:
                self.node.parent.value[new_value] = self.node.parent.value.pop(old_key)
        else:
            self.node.value = new_value
            if self.node.parent:
                self.node.parent.value[self.node.key] = new_value

        # Call the on_change function to trigger saving
        self.root_node.on_change()


class SettingsTree(toga.Box):
    def __init__(
        self,
        root_node,
        node=None,
        style=Pack(direction=COLUMN, padding=(5, 5, 5, 15)),
        depth=0,
    ):
        super().__init__(style=style)
        self.root_node = root_node
        self.node = node if node is not None else root_node
        self.depth = depth

        # Check for backup file only at the root level
        if depth == 0:
            import asyncio

            asyncio.create_task(self._check_backup_file())

        self.create_widgets()

        # Only add reset button at the root level
        if depth == 0 and hasattr(root_node, "example_yaml"):
            self._add_reset_button()

    async def _check_backup_file(self):
        # Check if a backup file exists for the current settings file
        if hasattr(self.root_node, "yaml_file"):
            backup_file = f"{self.root_node.yaml_file}.backup"
            if os.path.exists(backup_file):
                # First, show an alert explaining the backup file situation
                backup_alert = await self.window.dialog(
                    toga.QuestionDialog(
                        "Backup Settings Found",
                        "A backup of your previous settings was created due to "
                        "a configuration error. "
                        "Would you like to save these backup settings to review later?",
                    )
                )

                if backup_alert:
                    # Prompt user to save the backup file
                    save_dialog = toga.SaveFileDialog(
                        title="Save Backup Settings",
                        suggested_filename=os.path.basename(backup_file),
                    )

                    save_path = await self.window.dialog(save_dialog)

                    if save_path:
                        # Copy backup file to user-selected location
                        import shutil

                        shutil.copy2(backup_file, save_path)

                        # Delete the backup file
                        os.remove(backup_file)

                        # Show confirmation dialog
                        await self.window.dialog(
                            toga.InfoDialog(
                                "Backup Saved", f"Backup settings saved to {save_path}"
                            )
                        )

    def _add_reset_button(self):
        reset_box = toga.Box(style=Pack(direction=ROW, padding=(10, 0)))
        save_button = toga.Button(
            "Backup Settings",
            on_press=self._save_settings,
            style=Pack(flex=1, padding_right=5),
        )
        reset_button = toga.Button(
            "Reset to Defaults", on_press=self._reset_to_defaults, style=Pack(flex=1)
        )
        reset_box.add(save_button)
        reset_box.add(reset_button)
        self.add(reset_box)

    async def _reset_to_defaults(self, widget):
        # Confirm reset with user
        confirm_dialog = toga.QuestionDialog(
            title="Reset to Defaults",
            message="Are you sure you want to reset all settings to defaults?",
        )

        result = await self.window.dialog(confirm_dialog)

        if result:
            # Reload from example yaml
            if hasattr(self.root_node, "example_yaml"):
                try:
                    # Reload the entire data source from the example yaml
                    import yaml

                    with open(self.root_node.example_yaml) as file:
                        example_data = yaml.safe_load(file)

                    # Update the root node's value and recreate widgets
                    self.root_node.value = example_data
                    self.root_node.children.clear()
                    self.root_node._add_children()

                    # Save the new defaults
                    self.root_node.save_to_yaml()

                    # Recreate the entire widget tree
                    self.create_widgets()

                    await self.window.dialog(
                        toga.InfoDialog(
                            title="Reset Successful",
                            message="Settings have been reset to defaults.",
                        )
                    )
                except Exception as e:
                    await self.window.dialog(
                        toga.ErrorDialog(
                            title="Reset Failed",
                            message=f"Could not reset settings: {str(e)}",
                        )
                    )

    async def _save_settings(self, widget):
        # Open a save file dialog
        save_dialog = toga.SaveFileDialog(
            title="Save Settings", suggested_filename="settings.yaml"
        )

        file_path = await self.window.dialog(save_dialog)

        if file_path:
            try:
                # Save the current settings to the selected file
                import yaml

                with open(file_path, "w") as file:
                    yaml.safe_dump(self.root_node.to_dict(), file)

                await self.window.dialog(
                    toga.InfoDialog(
                        title="Save Successful",
                        message=f"Settings saved to {file_path}",
                    )
                )
            except Exception as e:
                await self.window.dialog(
                    toga.ErrorDialog(
                        title="Save Failed",
                        message=f"Could not save settings: {str(e)}",
                    )
                )

    def create_widgets(self):
        self.children.clear()
        self.add(SchemaNodeWidget(self.root_node, self.node))

        if isinstance(self.node.value, (dict, list)):
            for child in self.node.children:
                self.add_node(child=child)
        self.node.add_listener(self)

    def remove_node(self, child=None, **kwargs):
        self.parent.remove(self)

    def add_node(self, key=None, child=None, **kwargs):
        self.add(SettingsTree(self.root_node, node=child, depth=self.depth + 1))
