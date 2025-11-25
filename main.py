import ast
import argparse
import os
import shutil
import json
import keyword
import tempfile
from pathlib import Path
from difflib import unified_diff
from typing import List, Tuple, Dict, Set

# 1. Validate Python identifier rules
def is_valid_identifier(name: str) -> bool:
    return name.isidentifier() and not keyword.iskeyword(name)

# 2. Read file contents (utf-8) safely
def read_text(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

# 3. Write via tmp → move for atomic replace
def write_file_atomic(path: str, content: str) -> None:
    dir_path = os.path.dirname(path) or '.'
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', 
                                     dir=dir_path, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    shutil.move(tmp_path, path)

# 4. Parse source with ast.parse() with filename for building
def parse_to_ast(source: str, filename: str = '<unknown>') -> ast.AST:
    return ast.parse(source, filename=filename, type_comments=True)

# 5. ast.unparse() to get source back
def ast_to_source(tree: ast.AST) -> str:
    return ast.unparse(tree)

# 6. Locate Name, Attribute, FunctionDef, ClassDef, arg
def find_identifiers(tree: ast.AST, old_name: str) -> List[Tuple[int, int, str]]:
    occurrences = []
    
    class IdentifierFinder(ast.NodeVisitor):
        def visit_Name(self, node):
            if node.id == old_name:
                occurrences.append((node.lineno, node.col_offset, 'Name'))
            self.generic_visit(node)
        
        def visit_FunctionDef(self, node):
            if node.name == old_name:
                occurrences.append((node.lineno, node.col_offset, 'FunctionDef'))
            self.generic_visit(node)
        
        def visit_AsyncFunctionDef(self, node):
            if node.name == old_name:
                occurrences.append((node.lineno, node.col_offset, 'AsyncFunctionDef'))
            self.generic_visit(node)
        
        def visit_ClassDef(self, node):
            if node.name == old_name:
                occurrences.append((node.lineno, node.col_offset, 'ClassDef'))
            self.generic_visit(node)
        
        def visit_Attribute(self, node):
            if node.attr == old_name:
                occurrences.append((node.lineno, node.col_offset, 'Attribute'))
            self.generic_visit(node)
        
        def visit_arg(self, node):
            if node.arg == old_name:
                occurrences.append((node.lineno, node.col_offset, 'arg'))
            self.generic_visit(node)
    
    IdentifierFinder().visit(tree)
    return occurrences

# 7. Build ast.NodeTransformer
def create_renamer(old_name: str, new_name: str) -> ast.NodeTransformer:
    
    class Renamer(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id == old_name:
                node.id = new_name
            return node
        
        def visit_FunctionDef(self, node):
            if node.name == old_name:
                node.name = new_name
            self.generic_visit(node)
            return node
        
        def visit_AsyncFunctionDef(self, node):
            if node.name == old_name:
                node.name = new_name
            self.generic_visit(node)
            return node
        
        def visit_ClassDef(self, node):
            if node.name == old_name:
                node.name = new_name
            self.generic_visit(node)
            return node
        
        def visit_Attribute(self, node):
            if node.attr == old_name:
                node.attr = new_name
            self.generic_visit(node)
            return node
        
        def visit_arg(self, node):
            if node.arg == old_name:
                node.arg = new_name
            return node
    
    return Renamer()

# 8. Apply transformer and return modified tree
def apply_rename_to_tree(tree: ast.AST, renamer: ast.NodeTransformer) -> ast.AST:
    return renamer.visit(tree)

# 9. Unified diff review
def generate_diff(original: str, modified: str, path: str) -> str:
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    diff = unified_diff(orig_lines, mod_lines, 
                       fromfile=f'a/{path}', tofile=f'b/{path}', lineterm='')
    return ''.join(diff)

# 10. Print diffs, colorize or annotate
def preview_changes(changes: Dict[str, Tuple[str, str]]) -> None:
    for path, (original, modified) in changes.items():
        if original != modified:
            print(f"\n{'='*60}")
            print(f"File: {path}")
            print('='*60)
            diff = generate_diff(original, modified, path)
            print(diff if diff else "No changes")

# 11. Recursive .py discovery
def collect_py_files(root: str) -> List[str]:
    py_files = []
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if fname.endswith('.py'):
                py_files.append(os.path.join(dirpath, fname))
    return py_files

# 12. Copy file and record in manifest
def backup_file(path: str, backup_dir: str, manifest: Dict) -> None:
    backup_path = os.path.join(backup_dir, os.path.basename(path) + '.bak')
    counter = 1
    while os.path.exists(backup_path):
        backup_path = os.path.join(backup_dir, 
                                   f"{os.path.basename(path)}.bak.{counter}")
        counter += 1
    shutil.copy2(path, backup_path)
    manifest[path] = backup_path

# 13. Save manifest as .json of backups
def record_manifest(manifest_path: str, entries: Dict) -> None:
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, indent=2)

# 14. Undo using manifest entries
def restore_backups(manifest_path: str) -> None:
    if not os.path.exists(manifest_path):
        print(f"No manifest found at {manifest_path}")
        return
    
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    
    for original, backup in manifest.items():
        if os.path.exists(backup):
            shutil.copy2(backup, original)
            print(f"Restored: {original}")
        else:
            print(f"Backup not found: {backup}")

def safe_process_file(path: str, old: str, new: str, backup_dir: str) -> Tuple[str, str, bool]:
    try:                #  Full per-file pipeline (read→parse→find→transform→diff→backup→write)
        original = read_text(path)
        tree = parse_to_ast(original, path)
        
        occurrences = find_identifiers(tree, old)
        if not occurrences:
            return original, original, False
        
        renamer = create_renamer(old, new)
        modified_tree = apply_rename_to_tree(tree, renamer)
        modified = ast_to_source(modified_tree)
        
        return original, modified, True
    except Exception as e:
        print(f"Error processing {path}: {e}")
        return "", "", False

# 16. Totals: files touched, occurrences, failures
def summarize_stats(changes: Dict[str, Tuple[str, str]]) -> Dict:
    files_modified = sum(1 for o, m in changes.values() if o != m)
    return {
        'files_scanned': len(changes),
        'files_modified': files_modified,
        'files_unchanged': len(changes) - files_modified
    }

# 17. Simple y/n prompt for destructive ops
def confirm(prompt: str) -> bool:
    response = input(f"{prompt} (y/n): ").strip().lower()
    return response in ('y', 'yes')

# 18. Parse CLI flags and validate inputs
def parse_args():
    parser = argparse.ArgumentParser(description='AST-Safe Rename Tool - Refactor Python identifiers safely')
    parser.add_argument('--old', help='Identifier to rename')
    parser.add_argument('--new', help='New identifier name')
    parser.add_argument('--path', default='.', help='Root directory for scanning')
    parser.add_argument('--preview', action='store_true', help='Show diffs without writing')
    parser.add_argument('--apply', action='store_true', help='Write updated files')
    parser.add_argument('--undo', action='store_true', help='Restore backups')
    parser.add_argument('--manifest', default='.rename_manifest.json', help='Manifest file path')

    args = parser.parse_args()

    if args.undo:
        return args

    if not args.old or not args.new:
        parser.error("--old and --new are required unless using --undo")

    if args.old == args.new:
        parser.error("--old and --new must be different")

    if not is_valid_identifier(args.old):
        parser.error(f"Invalid identifier: {args.old}")
    if not is_valid_identifier(args.new):
        parser.error(f"Invalid identifier: {args.new}")

    return args

# 19. Orchestrate scanning, previews, backups, apply/undo, and summary
def main() -> int:
    args = parse_args()
    
    # Handle undo
    if args.undo:
        restore_backups(args.manifest)
        return 0
    
    # Collect files
    print(f"Scanning Python files in: {args.path}")
    py_files = collect_py_files(args.path)
    print(f"Found {len(py_files)} Python files")
    
    if not py_files:
        print("No Python files found")
        return 0
    
    # Process files
    backup_dir = tempfile.mkdtemp(prefix='ast_rename_backup_')
    manifest = {}
    changes = {}
    
    for path in py_files:
        original, modified, has_changes = safe_process_file(
            path, args.old, args.new, backup_dir
        )
        if original:
            changes[path] = (original, modified)
            if has_changes and args.apply:
               backup_file(path, backup_dir, manifest)
    
    # Preview
    if args.preview or not args.apply:
        preview_changes(changes)
        stats = summarize_stats(changes)
        print(f"\n{'='*60}")
        print(f"Summary: {stats['files_modified']} files to modify, " 
              f"{stats['files_unchanged']} unchanged")
        print('='*60)
        
        if not args.apply:
            print("\nUse --apply to write changes")
            return 0
    
    # Apply changes
    if args.apply:
        if not confirm("Apply changes to files?"):
            print("Aborted")
            return 1
        
        for path, (original, modified) in changes.items():
            if original != modified:
                write_file_atomic(path, modified)
                print(f"Modified: {path}")
        
        if manifest:
            record_manifest(args.manifest, manifest)
            print(f"\nBackup manifest saved: {args.manifest}")
            print(f"Use --undo to restore original files")
        
        stats = summarize_stats(changes)
        print(f"\nCompleted: {stats['files_modified']} files modified")
    
    return 0

def exit_with_code(success: bool) -> int:        # 20. Return CI-friendly exit codes
    return 0 if success else 1

if __name__ == '__main__':
    try:
        exit_code = main()
        exit(exit_code)
    except KeyboardInterrupt:
        print("\nOperation cancelled")
        exit(1)
    except Exception as e:
        print(f"Fatal error: {e}")
        exit(1)
