import toga
from schema import Schema
from toga.platform import get_platform_factory

import togax_settings

TOGA_PLATFORM = get_platform_factory().__name__

YOUR_SCHEMA = Schema(
    {
        "name": str,
        "age": int,
        "weight": float,
    }
)


class ExampleCustomDataSourceApp(toga.App):
    def startup(self):
        self.main_window = toga.MainWindow(title=self.formal_name)

        # Load data from YAML file
        self.data_source = togax_settings.SchemaDataSource.from_yaml(
            "Simple Settings",
            "simple/small.yaml",
            # Comment the line above and use the line below in real apps
            # self.paths.config / "small.yaml",
            YOUR_SCHEMA.schema,
            example_yaml=self.paths.app / "example.yaml",
        )

        # Create widgets based on the data source
        box = togax_settings.SettingsTree(self.data_source)

        if TOGA_PLATFORM == "toga_textual.factory":
            self.main_window.content = box
        else:
            # Create a scroll container for the box when not using textual
            scroll_container = toga.ScrollContainer(content=box)
            self.main_window.content = scroll_container

        self.main_window.show()


def main():
    return ExampleCustomDataSourceApp(
        "Custom Data Source", "org.example.customdatasource"
    )


if __name__ == "__main__":
    app = main()
    app.main_loop()
