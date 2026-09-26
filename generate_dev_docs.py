# Script for generating some of documents in `dev-docs` from Misago's code
import ast
import os
import re
import sys
from argparse import ArgumentParser
from dataclasses import dataclass, field
from glob import glob
from importlib import import_module
from io import StringIO
from pathlib import Path
from textwrap import dedent, indent

HOOKS_MODULES = (
    "misago.attachments.hooks",
    "misago.categories.hooks",
    "misago.context_processors.hooks",
    "misago.likes.hooks",
    "misago.metatags.hooks",
    "misago.moderation.hooks",
    "misago.notifications.hooks",
    "misago.oauth2.hooks",
    "misago.parser.hooks",
    "misago.permissions.hooks",
    "misago.polls.hooks",
    "misago.postedits.hooks",
    "misago.posting.hooks",
    "misago.privatethreads.hooks",
    "misago.solutions.hooks",
    "misago.threads.hooks",
    "misago.threadevents.hooks",
    "misago.users.hooks",
)
PLUGIN_MANIFEST = "misago.plugins.manifest.MisagoPlugin"
OUTLETS_ENUM = "misago.plugins.enums.PluginOutlet"

BASE_PATH = Path(__file__).parent
DOCS_PATH = BASE_PATH / "dev-docs"
PLUGINS_PATH = DOCS_PATH / "plugins"
PLUGINS_HOOKS_PATH = PLUGINS_PATH / "hooks"

KEEP_PLUGINS_HOOKS_PATHS = (
    "index.md",
    "action-hook.md",
    "filter-hook.md",
)


@dataclass
class FilesReport:
    outdated_files: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)

    def get_exit_code(self) -> int:
        if self.missing_files or self.outdated_files or self.deleted_files:
            return 1

        return 0


def get_hooks_modules_from_codebase() -> dict[str, Path]:
    hooks_modules: dict[str, Path] = {}
    for init_path in glob(f"{BASE_PATH}/misago/*/hooks/__init__.py"):
        init_path = Path(init_path)
        module_name = ".".join(init_path.parent.relative_to(BASE_PATH).parts)
        hooks_modules[module_name] = init_path
    return hooks_modules


def get_module_all_names(module: ast.Module) -> list[str] | None:
    for item in module.body:
        if not isinstance(item, ast.Assign):
            continue

        if not item.targets or not isinstance(item.targets[0], ast.Name):
            continue

        if item.targets[0].id != "__all__":
            continue

        if not isinstance(item.value, (ast.List, ast.Tuple)):
            continue

        return [
            element.value
            for element in item.value.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        ]

    return None


def get_module_hook_names(module: ast.Module) -> list[str]:
    hook_names: list[str] = []
    for item in module.body:
        if not isinstance(item, ast.Assign):
            continue

        if not isinstance(item.value, ast.Call):
            continue

        for target in item.targets:
            if isinstance(target, ast.Name) and target.id.endswith("_hook"):
                hook_names.append(target.id)

    return hook_names


def validate_hooks_modules() -> list[str]:
    """Verify that every hook in the codebase is reachable from HOOKS_MODULES.

    The reference is built by walking HOOKS_MODULES, so a hooks package that is
    missing from it - or a hook that isn't re-exported from its package's
    `__init__.py` - is silently left undocumented instead of failing the build.
    """
    problems: list[str] = []
    declared_modules = set(HOOKS_MODULES)
    codebase_modules = get_hooks_modules_from_codebase()

    for module_name in sorted(codebase_modules):
        init_path = codebase_modules[module_name]

        if module_name not in declared_modules:
            problems.append(
                f"'{module_name}' exists in the codebase "
                f"but is missing from HOOKS_MODULES"
            )
            continue

        all_names = get_module_all_names(parse_python_file(init_path))
        if all_names is None:
            problems.append(f"'{module_name}': '__init__.py' doesn't define '__all__'")
            continue

        exported_names = set(all_names)
        for hook_path in sorted(init_path.parent.glob("*.py")):
            if hook_path.name == "__init__.py":
                continue

            for hook_name in get_module_hook_names(parse_python_file(hook_path)):
                if hook_name not in exported_names:
                    problems.append(
                        f"'{hook_name}' is defined in '{format_path(hook_path)}' "
                        f"but is not exported from '{module_name}'"
                    )

    for module_name in sorted(declared_modules - set(codebase_modules)):
        problems.append(
            f"'{module_name}' is in HOOKS_MODULES but doesn't exist in the codebase"
        )

    return problems


def print_hooks_validation_message(problems: list[str]):
    lines: list[str] = [
        "",
        "The hooks reference can't be generated because its sources are invalid:",
        "",
    ]

    for problem in problems:
        lines.append(f"- {problem}")

    problems_noun = "problem" if len(problems) == 1 else "problems"
    lines.append("")
    lines.append(f"{len(problems)} {problems_noun} found.")

    sys.stderr.write("\n".join(lines))


def get_hook_example_blocks(docstring: str) -> list[str]:
    return re.findall(r"```python\n(.*?)```", docstring, re.S)


def validate_hook_examples() -> list[str]:
    """Verify that the examples in hooks' docstrings are valid Python.

    Example blocks are rendered verbatim into the generated reference, so a typo
    ships as broken documentation that plugin authors then copy. An unclosed code
    fence is reported too, because it swallows the rest of the generated page.
    """
    problems: list[str] = []

    for hooks_module in HOOKS_MODULES:
        init_path = module_path_to_init_path(hooks_module)

        for hook_path in sorted(init_path.parent.glob("*.py")):
            if hook_path.name == "__init__.py":
                continue

            for class_def in parse_python_file(hook_path).body:
                if not isinstance(class_def, ast.ClassDef):
                    continue

                docstring = ast.get_docstring(class_def)
                if not docstring:
                    continue

                if docstring.count("```") % 2:
                    problems.append(
                        f"'{format_path(hook_path)}': '{class_def.name}' has an "
                        f"unclosed code fence in its docstring"
                    )

                for block in get_hook_example_blocks(docstring):
                    try:
                        ast.parse(dedent(block))
                    except SyntaxError as error:
                        problems.append(
                            f"'{format_path(hook_path)}': '{class_def.name}' has an "
                            f"example that isn't valid Python "
                            f"(line {error.lineno}: {error.msg})"
                        )

    return problems


def main(check: bool):
    problems = validate_hooks_modules() + validate_hook_examples()
    if problems:
        print_hooks_validation_message(problems)
        sys.stdout.write("\n")
        return 1

    files_content: dict[Path, str] = {}
    files_content.update(generate_plugin_manifest_reference())
    files_content.update(generate_hooks_reference())
    files_content.update(generate_outlets_reference())

    report = compare_files(files_content)
    exit_code = report.get_exit_code()

    if check:
        if exit_code:
            print_check_message(report)
        else:
            sys.stdout.write("\nNothing to change - all files up to date")
    else:
        write_files(files_content)
        print_completed_message(report)

    sys.stdout.write("\n")
    return exit_code


def compare_files(files_content):
    report = FilesReport()

    # Missing or updated
    for file_path, file_content in files_content.items():
        if file_path.is_file():
            with open(file_path, "r") as fp:
                if fp.read() != file_content:
                    report.outdated_files.append(format_path(file_path))
        else:
            report.missing_files.append(format_path(file_path))

    # Deleted
    for path in glob(f"{PLUGINS_HOOKS_PATH}/*.md"):
        filename = str(path).split("/")[-1].lower()
        if filename in KEEP_PLUGINS_HOOKS_PATHS:
            continue

        if Path(path) not in files_content:
            report.deleted_files.append(format_path(path))

    return report


def format_path(path: Path) -> str:
    return str(path)[len(str(BASE_PATH)) + 1 :]


def print_check_message(report):
    lines: list[str] = []

    if report.outdated_files:
        lines.append("")
        for file_name in report.outdated_files:
            lines.append(f"would update {file_name}")

        files = "file" if len(report.outdated_files) == 1 else "files"
        lines.append(f"\n{len(report.outdated_files)} {files} would be updated.")

    if report.missing_files:
        lines.append("")
        for file_name in report.missing_files:
            lines.append(f"would create {file_name}")

        files = "file" if len(report.missing_files) == 1 else "files"
        lines.append(f"\n{len(report.missing_files)} {files} would be created.")

    if report.deleted_files:
        lines.append("")
        for file_name in report.deleted_files:
            lines.append(f"would delete {file_name}")

        files = "file" if len(report.deleted_files) == 1 else "files"
        lines.append(f"\n{len(report.deleted_files)} {files} would be deleted.")

    sys.stderr.write("\n".join(lines))


def print_completed_message(report):
    if report.outdated_files:
        for file_name in report.outdated_files:
            sys.stderr.write(f"updated {file_name}\n")

    if report.missing_files:
        for file_name in report.missing_files:
            sys.stderr.write(f"created {file_name}\n")

    if report.deleted_files:
        for file_name in report.deleted_files:
            sys.stderr.write(f"deleted {file_name}\n")

    message: list[str] = []

    if report.missing_files and report.outdated_files:
        files = "file" if len(report.outdated_files) == 1 else "files"
        message.append(
            f"Saved {len(report.missing_files)} new and {len(report.outdated_files)} updated {files}."
        )
    elif report.missing_files:
        files = "file" if len(report.missing_files) == 1 else "files"
        message.append(f"Saved {len(report.missing_files)} new {files}.")
    elif report.outdated_files:
        files = "file" if len(report.outdated_files) == 1 else "files"
        message.append(f"Updated {len(report.outdated_files)} {files}.")

    if report.deleted_files:
        files = "file" if len(report.deleted_files) == 1 else "files"
        message.append(f"Deleted {len(report.deleted_files)} {files}.")

    sys.stdout.write("\n")

    if message:
        sys.stdout.write(" ".join(message))
    else:
        sys.stdout.write("Nothing to change - all files up to date")


def write_files(files_content):
    for path in glob(f"{PLUGINS_HOOKS_PATH}/*.md"):
        filename = str(path).split("/")[-1].lower()
        if filename not in KEEP_PLUGINS_HOOKS_PATHS:
            os.unlink(path)

    for file_path, file_content in files_content.items():
        with open(file_path, "w") as fp:
            fp.write(file_content)


def generate_plugin_manifest_reference():
    manifest_path, manifest_attr = PLUGIN_MANIFEST.rsplit(".", 1)
    manifest_type = getattr(import_module(manifest_path), manifest_attr)

    file_name = PLUGINS_PATH / "plugin-manifest-reference.md"

    file_content = StringIO()
    file_content.write("# Plugin manifest reference")
    file_content.write("\n\n")
    file_content.write(indent_docstring_headers(dedent(manifest_type.__doc__)).strip())

    return {file_name: file_content.getvalue()}


def generate_hooks_reference():
    hooks_data: dict[str, dict[str, ast.Module]] = {}
    for hooks_module in HOOKS_MODULES:
        init_path = module_path_to_init_path(hooks_module)
        hooks_data[hooks_module] = get_all_modules(init_path)

    file_name, content = generate_hooks_reference_index(hooks_data)
    hooks_ref_content = {file_name: content}

    for import_from, module_hooks in hooks_data.items():
        for hook_name, hook_module in module_hooks.items():
            file_name, content = generate_hook_reference(
                import_from, hook_name, hook_module
            )
            hooks_ref_content[file_name] = content

    return hooks_ref_content


def generate_hooks_reference_index(hooks_data: dict[str, dict[str, ast.Module]]):
    file_name = PLUGINS_HOOKS_PATH / "reference.md"

    file_content = StringIO()
    file_content.write("# Built-in hooks reference")
    file_content.write("\n\n")
    file_content.write(
        "This document contains a list of all standard plugin hooks existing in Misago."
    )
    file_content.write("\n\n")
    file_content.write(
        "Hooks instances are importable from the following Python modules:"
    )

    file_content.write("\n")
    for module_name in sorted(hooks_data):
        file_content.write(f"\n- [`{module_name}`](#{slugify_name(module_name)})")

    for module_name, module_hooks in hooks_data.items():
        file_content.write("\n\n\n")
        file_content.write(f"## `{module_name}`")
        file_content.write("\n\n")
        file_content.write(f"`{module_name}` defines the following hooks:")
        file_content.write("\n")

        for module_hook in sorted(module_hooks):
            file_content.write(
                f"\n- [`{module_hook}`](./{slugify_name(module_hook)}.md)"
            )

    return file_name, file_content.getvalue()


def generate_hook_reference(import_from: str, hook_name: str, hook_module: ast.Module):
    hook_filename = f"{slugify_name(hook_name)}.md"

    module_classes = {}
    for item in hook_module.body:
        if isinstance(item, ast.ClassDef):
            module_classes[item.name] = item

        if (
            isinstance(item, ast.Expr)
            and item.value
            and isinstance(item.value, ast.Constant)
            and isinstance(item.value.value, str)
        ):
            if module_docstring is not None:
                raise ValueError(
                    f"'{hook_name}': module with hook defines multiple docstrings."
                )
            module_docstring = parse_hook_docstring(item.value.value)

    hook_type: str | None = None
    hook_ast: ast.ClassDef | None = None
    hook_action_ast: ast.ClassDef | None = None
    hook_filter_ast: ast.ClassDef | None = None
    for class_name, class_ast in module_classes.items():
        class_hook_type = is_class_base_hook(class_ast)
        if class_hook_type:
            hook_ast = class_ast
            hook_type = class_hook_type
        elif is_class_protocol(class_ast):
            if class_name.endswith("HookAction"):
                hook_action_ast = class_ast
            elif class_name.endswith("HookFilter"):
                hook_filter_ast = class_ast

    hook_docstring: HookDocstring | None = None
    hook_ast_docstring = get_class_docstring(hook_ast)
    if hook_ast_docstring:
        hook_docstring = parse_hook_docstring(hook_ast_docstring)

    file_name = PLUGINS_HOOKS_PATH / hook_filename
    file_content = StringIO()
    file_content.write(f"# `{hook_name}`")
    file_content.write("\n\n")

    if hook_docstring and hook_docstring.description:
        file_content.write(hook_docstring.description)
    elif hook_type == "ACTION":
        file_content.write(f"`{hook_name}` is an **action** hook.")
    elif hook_type == "FILTER":
        file_content.write(f"`{hook_name}` is a **filter** hook.")

    file_content.write("\n\n\n")
    file_content.write("## Location")
    file_content.write("\n\n")
    file_content.write(f"This hook can be imported from `{import_from}`:")
    file_content.write("\n\n")
    file_content.write("```python")
    file_content.write("\n")
    file_content.write(f"from {import_from} import {hook_name}")
    file_content.write("\n")
    file_content.write("```")

    if hook_type == "ACTION":
        file_content.write("\n\n\n")
        file_content.write("## Action")

        if hook_action_ast:
            hook_cropped = hook_name
            if hook_cropped.endswith("_hook"):
                hook_cropped = hook_cropped[:-5]

            hook_action_signature = get_callable_class_signature(hook_action_ast)
            if hook_action_signature:
                hook_action_args, hook_action_returns = hook_action_signature
            else:
                hook_action_args = ""
                hook_action_returns = "Unknown"

            file_content.write("\n\n")
            file_content.write("```python")
            file_content.write("\n")
            file_content.write(
                f"def custom_{hook_cropped}_filter({hook_action_args}){hook_action_returns}:"
            )
            file_content.write("\n")
            file_content.write("    ...")
            file_content.write("\n")
            file_content.write("```")

            hook_action_docstring = get_class_docstring(hook_action_ast)
            if hook_action_docstring:
                file_content.write("\n\n")
                file_content.write(
                    indent_docstring_headers(hook_action_docstring, level=2)
                )
        else:
            file_content.write("_This section is empty._")

    if hook_type == "FILTER":
        file_content.write("\n\n\n")
        file_content.write("## Filter")

        if hook_filter_ast:
            hook_cropped = hook_name
            if hook_cropped.startswith("filter_"):
                hook_cropped = hook_cropped[7:]
            if hook_cropped.endswith("_hook"):
                hook_cropped = hook_cropped[:-5]

            hook_filter_signature = get_callable_class_signature(hook_filter_ast)
            if hook_filter_signature:
                hook_filter_args, hook_filter_returns = hook_filter_signature
            else:
                hook_filter_args = ""
                hook_filter_returns = "Unknown"

            file_content.write("\n\n")
            file_content.write("```python")
            file_content.write("\n")
            file_content.write(
                f"def custom_{hook_cropped}_filter({hook_filter_args}){hook_filter_returns}:"
            )
            file_content.write("\n")
            file_content.write("    ...")
            file_content.write("\n")
            file_content.write("```")

            hook_filter_docstring = get_class_docstring(hook_filter_ast)
            if hook_filter_docstring:
                file_content.write("\n\n")
                file_content.write(
                    indent_docstring_headers(hook_filter_docstring, level=2)
                )
        else:
            file_content.write("_This section is empty._")

        file_content.write("\n\n\n")
        file_content.write("## Action")

        if hook_action_ast:
            hook_cropped = hook_name
            if hook_cropped.endswith("_hook"):
                hook_cropped = hook_cropped[:-5]

            hook_action_signature = get_callable_class_signature(hook_action_ast)
            if hook_action_signature:
                hook_action_args, hook_action_returns = hook_action_signature
            else:
                hook_action_args = ""
                hook_action_returns = "Unknown"

            file_content.write("\n\n")
            file_content.write("```python")
            file_content.write("\n")
            file_content.write(
                f"def {hook_cropped}_action({hook_action_args}){hook_action_returns}:"
            )
            file_content.write("\n")
            file_content.write("    ...")
            file_content.write("\n")
            file_content.write("```")

            hook_action_docstring = get_class_docstring(hook_action_ast)
            if hook_action_docstring:
                file_content.write("\n\n")
                file_content.write(
                    indent_docstring_headers(hook_action_docstring, level=2)
                )

        else:
            file_content.write("_This section is empty._")

    if hook_docstring and hook_docstring.examples:
        for example_title, example_text in hook_docstring.examples.items():
            file_content.write("\n\n\n")
            file_content.write(f"## {example_title}")
            file_content.write("\n\n")
            file_content.write(example_text)

    return file_name, file_content.getvalue()


def is_class_base_hook(class_def: ast.ClassDef) -> str | None:
    if not class_def.bases:
        return None

    for base in class_def.bases:
        if (
            isinstance(base, ast.Subscript)
            and isinstance(base.value, ast.Name)
            and isinstance(base.value.id, str)
        ):
            if base.value.id == "ActionHook":
                return "ACTION"
            if base.value.id == "FilterHook":
                return "FILTER"

    return None


def is_class_protocol(class_def: ast.ClassDef) -> bool:
    if not class_def.bases or len(class_def.bases) != 1:
        return False

    return (
        isinstance(class_def.bases[0], ast.Name)
        and isinstance(class_def.bases[0].id, str)
        and class_def.bases[0].id == "Protocol"
    )


@dataclass
class HookDocstring:
    description: str | None
    examples: dict[str, str] | None


def parse_hook_docstring(docstring: str) -> HookDocstring:
    description: str | None = None
    examples: dict[str, str] = {}

    for block in split_docstring(docstring):
        if block[:5].strip().startswith("# ") and block.lstrip("# ").lower().startswith(
            "example"
        ):
            example_name = block[: block.index("\n")].strip("# ")
            example_block = block[block.index("\n") :].strip()
            examples[example_name] = example_block
        elif not block[:5].strip().startswith("# "):
            description = block

    return HookDocstring(description=description, examples=examples or None)


def generate_outlets_reference():
    outlets_path, outlets_attr = OUTLETS_ENUM.rsplit(".", 1)
    outlets_enum = getattr(import_module(outlets_path), outlets_attr)
    outlets_dict = {outlet.name: outlet.value for outlet in outlets_enum}

    file_name = PLUGINS_PATH / "template-outlets-reference.md"

    file_content = StringIO()
    file_content.write("# Built-in template outlets reference")
    file_content.write("\n\n")
    file_content.write(
        "This document contains a list of all built-in template outlets in Misago."
    )
    for outlet_name, outlet_contents in outlets_dict.items():
        file_content.write("\n\n\n")
        file_content.write(f"## `{outlet_name}`")
        file_content.write("\n\n")
        file_content.write(outlet_contents)

    return {file_name: file_content.getvalue()}


def get_callable_class_signature(class_def: ast.ClassDef) -> tuple[str, str | None]:
    for item in class_def.body:
        if not isinstance(item, ast.FunctionDef):
            continue
        if item.name != "__call__":
            continue

        item_args = ast.unparse(item.args)
        if item_args.startswith("self, "):
            item_args = item_args[6:]

        if len(item_args) > 70:
            item_args = item_args.replace(", ", ",\n")
            # Hack to fix invalid linebreaks in `[T1, T2]`...
            offset = 0
            for _ in range(item_args.count("[")):
                position = item_args.find("[", offset)
                end_position = item_args.find("]", position)
                if ",\n" in item_args[position:end_position]:
                    item_args_copy = item_args
                    item_args = item_args_copy[:position]
                    item_args += item_args_copy[position:end_position].replace(
                        ",\n", ", "
                    )
                    item_args += item_args_copy[end_position:]
                offset = position + 1
            item_args = "\n" + indent(item_args, "    ") + ",\n"

        elif len(item_args) > 50:
            item_args = f"\n    {item_args}\n"

        if item.returns:
            item_returns = " -> " + ast.unparse(item.returns)
        else:
            item_returns = ""

        return item_args, item_returns

    return None


def get_class_docstring(class_def: ast.ClassDef) -> str | None:
    for item in class_def.body:
        if (
            isinstance(item, ast.Expr)
            and isinstance(item.value, ast.Constant)
            and isinstance(item.value.value, str)
        ):
            return dedent(item.value.value).strip()

    return None


def split_docstring(docstring: str) -> list[str]:
    blocks: list[str] = []
    block: str = ""
    in_code = False
    for line in docstring.strip().splitlines():
        if in_code:
            if line == "```":
                in_code = False
            block += line
        else:
            if line.startswith("```"):
                in_code = True
                block += line

            elif line.startswith("# "):
                if block:
                    blocks.append(wrap_docstring_lines(block.strip()))
                block = line

            else:
                block += line

        block += "\n"

    if block:
        blocks.append(wrap_docstring_lines(block))

    return blocks


def indent_docstring_headers(docstring: str, level: int = 1) -> str:
    in_code = False
    prefix = "#" * level

    new_docstring = ""
    for line in docstring.splitlines():
        if in_code:
            if line == "```":
                in_code = False
            new_docstring += line
        else:
            if line.startswith("```"):
                in_code = True
            if not in_code and line.startswith("#"):
                new_docstring += prefix
            new_docstring += line

        new_docstring += "\n"

    return wrap_docstring_lines(new_docstring.strip())


def wrap_docstring_lines(docstring: str) -> str:
    in_code = False
    new_docstring = ""
    previous_line = ""

    for line in docstring.splitlines():
        if in_code:
            new_docstring += line
            new_docstring += "\n"

            if line == "```":
                in_code = False
        else:
            if line.startswith("```"):
                in_code = True
                new_docstring += line
                new_docstring += "\n"
            elif line.startswith("#"):
                if new_docstring and not previous_line.startswith("#"):
                    new_docstring += "\n"
                new_docstring += line
                new_docstring += "\n\n"
            elif line:
                if new_docstring and not new_docstring.endswith("\n"):
                    new_docstring += " "
                new_docstring += line
            elif not previous_line.startswith("#"):
                while not new_docstring.endswith("\n\n"):
                    new_docstring += "\n"

            if line:
                previous_line = line

    return new_docstring.strip()


def get_all_modules(file_path: str) -> dict[str, ast.Module]:
    all_names: list[str] = []
    all_imports: dict[str, ast.Module] = {}

    file_ast: ast.Module = parse_python_file(file_path)
    for item in file_ast.body:
        if not isinstance(item, ast.Assign):
            continue  # Skip non-value assignment

        if not item.targets or not item.value:
            continue  # Skip value assignment without targets

        if item.targets[0].id != "__all__":
            continue  # Skip variables that aren't __all__

        if not isinstance(item.value, (ast.List, ast.Tuple)):
            continue  # Skip non-list or tuple

        for item_value in item.value.elts:
            if not isinstance(item_value, ast.Constant):
                raise ValueError(f"'{file_path}': '__all__' items must be constants.")
            if not isinstance(item_value.value, str):
                raise ValueError(f"'{file_path}': '__all__' items must be strings.")

            all_names.append(item_value.value)

    for item in file_ast.body:
        if not isinstance(item, ast.ImportFrom):
            continue  # Skip non-value assignment

        if len(item.names) != 1:
            continue

        import_name = item.names[0].name
        if import_name not in all_names:
            continue

        import_path = Path(file_path).parent / f"{item.module}.py"
        if not import_path.is_file():
            raise ValueError(f"'{file_path}': '{item.module}' could not be imported.")

        all_imports[import_name] = parse_python_file(import_path)

    for name in all_names:
        if name not in all_imports:
            raise ValueError(f"'{file_path}': import for '{name}' could not be found.")

    return {name: all_imports[name] for name in sorted(all_names)}


def parse_python_file(file_path: Path) -> ast.Module:
    with open(file_path, "r") as fp:
        return ast.parse(fp.read())


def module_path_to_init_path(module_path: str) -> Path:
    base_path = Path(BASE_PATH, *module_path.split("."), "__init__.py")
    if not base_path.is_file():
        raise ValueError(f"'{base_path}' doesn't exist or is not a file.")
    return base_path


def slugify_name(py_name: str) -> str:
    return py_name.replace(".", "-").replace("_", "-")


def create_args_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="Script for generating some of documents in `dev-docs` from Misago's code"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Don't generate the dev-docs files, just return the status. Return code 0 means"
            " nothing would change. Return code 1 means some files would be regenerated."
        ),
    )
    return parser


if __name__ == "__main__":
    parser = create_args_parser()
    args = parser.parse_args()
    sys.exit(main(args.check))
