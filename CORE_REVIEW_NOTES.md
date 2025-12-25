# Core Review - Imperfections Found and Fixes

## Imperfections Identified in Core/MainWindow.py

### 1. **Asyncio Import Issue**
- ❌ `import asyncio` at top level but only used in specific methods
- ✅ Move to local imports where needed

### 2. **Inconsistent Error Handling**
- ❌ Mix of try/except with and without logging
- ✅ Standardize error handling with consistent logging

### 3. **Code Duplication**
- ❌ `apply_workspace_selection` has duplicated logic
- ❌ Multiple similar try/except blocks
- ✅ Extract common patterns into helper methods

### 4. **Qt Resource Cleanup**
- ❌ QProcess objects not always properly deleted
- ❌ Timers not always stopped before deletion
- ✅ Ensure all Qt objects call `deleteLater()` properly

### 5. **Thread Safety Issues**
- ❌ Global `_latest_gui_instance` without proper synchronization
- ❌ `_workspace_dir_cache` access without consistent locking
- ✅ Use proper thread-safe patterns

### 6. **Incomplete Cleanup in closeEvent**
- ❌ BCASL thread stopped AFTER cancel_all_compilations
- ❌ No guarantee all processes are killed before exit
- ✅ Proper shutdown sequence: BCASL → Compilations → Background tasks

### 7. **Missing Null Checks**
- ❌ Many `getattr()` calls without proper None checks
- ✅ Add defensive checks before method calls

### 8. **Inconsistent Logging**
- ❌ Mix of `log_i18n()`, `_safe_log()`, and direct `log.append()`
- ✅ Standardize on single logging method

### 9. **Resource Leaks**
- ❌ QProcess objects created but not always tracked
- ❌ Timers created but not always stored for cleanup
- ✅ Maintain registry of all created resources

### 10. **Async/Await Complexity**
- ❌ `_run_coro_async()` is complex and error-prone
- ❌ Multiple async patterns mixed together
- ✅ Simplify to use QTimer for non-blocking operations

## Recommended Fixes

### Priority 1 (Critical)
1. Fix closeEvent shutdown sequence
2. Ensure all Qt objects are properly deleted
3. Fix thread safety of global variables

### Priority 2 (Important)
1. Standardize error handling
2. Remove code duplication
3. Add proper resource tracking

### Priority 3 (Nice to Have)
1. Simplify async patterns
2. Improve logging consistency
3. Add defensive null checks

## Files to Review
- ✅ Core/MainWindow.py - REVIEWED (many imperfections)
- ⏳ Core/init_ui.py - TO REVIEW
- ⏳ Core/preferences.py - TO REVIEW
- ⏳ Core/dialogs.py - TO REVIEW
- ⏳ Core/i18n.py - TO REVIEW
- ⏳ Core/Venv_Manager/Manager.py - TO REVIEW

## Summary
The Core module has several imperfections related to:
- Resource cleanup (Qt objects, processes, timers)
- Thread safety (global variables)
- Error handling consistency
- Code duplication
- Async complexity

These should be addressed to ensure stability and prevent resource leaks.
