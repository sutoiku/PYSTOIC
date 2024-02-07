import ast
import logging
import subprocess
from pathlib import Path

from .models import (
    Workbook,
    FileContext,
)


def member_is_excluded(name: str) -> bool:
    """
    Check if the given name should be excluded based on predefined patterns.

    Args:
        name: The name to check for exclusion

    Returns: True if the name should be excluded, False otherwise
    """
    return name.startswith("test_") or name.startswith("__")


def discover_to_be_exported_declarations(python_file: Path) -> list[str]:
    """
    Parses the given python file and returns a list of strings
    representing the names of the functions, classes and variables
    that should be exported in the `__init__.py` file.

    Args:
        python_file: Path to a python file

    Returns: list of strings
    """
    python_src = python_file.read_text()
    tree = ast.parse(python_src)
    exportable_declarations = []

    class DeclarationFinder(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            if not member_is_excluded(node.name):
                exportable_declarations.append(node.name)

        def visit_ClassDef(self, node):
            if not member_is_excluded(node.name):
                exportable_declarations.append(node.name)

        def visit_Assign(self, node):
            # Only consider top-level assignments by checking if the parent node is 'Module'
            if isinstance(node.parent, ast.Module):
                for target in node.targets:
                    if isinstance(target, ast.Name) and not member_is_excluded(
                        target.id
                    ):
                        exportable_declarations.append(target.id)

    # Add a parent attribute to each node that points to the parent node
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node

    # Create an instance of the node visitor and visit the AST
    finder = DeclarationFinder()
    finder.visit(tree)

    return sorted(list(set(exportable_declarations)))


AUTO_GENERATED_HEADER = "# THIS FILE WAS AUTOGENERATED BY setup.py"


def create_init_file_body(module_name: str, declarations: list[str]) -> str:
    """
    Creates the body of an `__init__.py` file for the given module name and list of declarations.

    Args:
        module_name: The name of the module, such as `blocks`
        declarations: The list of declarations to export

    Returns: A string representing the body of the `__init__.py` file
    """
    if len(declarations) == 0:
        return AUTO_GENERATED_HEADER

    import_statement = f'from .{module_name} import {", ".join(declarations)}'
    declaration_strings = [f"'{declaration}'" for declaration in declarations]
    all_statement = f'__all__ = [{", ".join(declaration_strings)}]'
    return "\n\n".join([AUTO_GENERATED_HEADER, import_statement, all_statement])


def setup_module_init_file(module_root: Path):
    parent_init_file = Path(module_root).parent / "__init__.py"
    if not parent_init_file.exists():
        parent_init_file.write_text(AUTO_GENERATED_HEADER)

    init_file = Path(module_root) / "__init__.py"
    if init_file.exists() and file_was_already_processed(init_file):
        logging.debug(f"Skipping {init_file} as it was already processed")
        return

    module_name = "blocks"
    python_module_file = Path(module_root) / f"{module_name}.py"

    if not python_module_file.exists():
        logging.error(f"Expected to find {python_module_file} but it does not exist")
        raise Exception(f"Expected to find {python_module_file} but it does not exist")

    exported_declarations = discover_to_be_exported_declarations(python_module_file)
    logging.debug(f"Exporting {exported_declarations} from {python_module_file}")

    init_file_body = create_init_file_body(module_name, exported_declarations)
    init_file.write_text(init_file_body)
    logging.info(f"Wrote {init_file}")


def remove_tests(python_src: str) -> str:
    def is_pytest_decorated(node) -> bool:
        def is_pytest_call(decorator):
            if isinstance(decorator, ast.Call):
                return is_pytest_call(decorator.func)
            elif isinstance(decorator, ast.Attribute):
                return is_pytest_call(decorator.value)
            elif isinstance(decorator, ast.Name):
                return decorator.id == "pytest"
            return False

        return any(is_pytest_call(decorator) for decorator in node.decorator_list)

    class RemoveTestsTransformer(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            # Remove functions starting with 'test_' by skipping their visit
            # i.e. not including them in the returned tree
            if node.name.startswith("test_") or is_pytest_decorated(node):
                return None
            return self.generic_visit(node)

    python_src = python_src.replace("import pytest", "")
    tree = ast.parse(python_src)
    cleaned_tree = RemoveTestsTransformer().visit(tree)
    return ast.unparse(cleaned_tree)


def remove_no_effect_nodes(source_code: str) -> str:
    class NoEffectNodeRemover(ast.NodeTransformer):
        def visit_Expr(self, node):
            # Check if the expression has a value that is not a function call
            # or other side-effect operations like yield
            if not isinstance(
                node.value, (ast.Call, ast.Yield, ast.YieldFrom, ast.Await)
            ):
                return None  # Remove the node by returning None
            return self.generic_visit(node)

    tree = ast.parse(source_code)
    cleaned_tree = NoEffectNodeRemover().visit(tree)
    return ast.unparse(cleaned_tree)


def patch_python_file(ctxt: FileContext):
    python_file = ctxt.path
    if AUTO_GENERATED_HEADER in ctxt.source:
        logging.info(f"Skipping {python_file} as it was already processed")
        return

    # This ensures that excluded and test blocks are not included in the production source
    python_src = ctxt.notebook.production_python_source

    # Apply patches
    python_src = remove_tests(python_src)
    python_src = remove_no_effect_nodes(python_src)
    python_src = "\n".join([AUTO_GENERATED_HEADER, python_src])

    python_file.write_text(python_src)


def lint_package():
    subprocess.run(["ruff", "--fix", "."], check=False)
    subprocess.run(["ruff", "format", "."], check=False)


def write_requirements_txt_if_needed(workbook: Workbook):
    requirements_txt = Path("requirements.txt")
    if requirements_txt.exists():
        logging.info(f"{requirements_txt} already exists, skipping")
        return
    else:
        logging.info(f"Writing {workbook.python_requirements} to {requirements_txt}...")
        requirements_txt.write_text("\n".join(workbook.python_requirements))


def file_was_already_processed(python_file: Path) -> bool:
    """
    Checks if the given python file was already processed
    by checking if it contains the auto-generated header.

    Args:
        python_file: Path to a python file

    Returns: True if the file was already processed, False otherwise
    """
    python_src = python_file.read_text()
    return AUTO_GENERATED_HEADER in python_src


def normalize_workbook(workbook: Workbook):
    python_files = workbook.python_files
    logging.info(f"Applying patches to python files: {python_files}")
    for python_file in python_files:
        file_ctxt = workbook.contextualize_file(python_file)
        patch_python_file(file_ctxt)

    module_roots = [nb.path for nb in workbook.python_notebooks]
    logging.info(f"Creating `__init__.py` in module roots: {module_roots}")
    for module_root in module_roots:
        setup_module_init_file(module_root)


def normalize_dir_structure(workbook: Workbook, package_name: str):
    package_root = workbook.path / package_name
    if package_root.exists():
        logging.info(f"Package root {package_root} already exists, skipping")
        return

    package_root.mkdir(exist_ok=False)
    subfolders: list[Path] = [wf.path for wf in workbook.workfolders]

    # Move each subfolder to the package root
    for subfolder in subfolders:
        target = package_root / subfolder.name
        logging.debug(f"Copying {subfolder} to {target}")
        subfolder.rename(target)

    package_root_init_file = package_root / "__init__.py"
    package_root_init_file.touch()
