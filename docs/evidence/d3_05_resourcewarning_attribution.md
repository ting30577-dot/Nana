# D3-05 shutdown warning attribution

Date: 2026-08-08

## Diagnostic command

The full unittest suite was run with `gc.DEBUG_UNCOLLECTABLE` enabled and the
same test discovery as the normal suite. It completed 353 tests with 2 skips
and no test failure. At interpreter shutdown, the debug output identified the
uncollectable graph as PySide6/Qt and legacy UI metadata, including
`PySide6.QtCore.Property`, `PySide6.QtCore.QMetaObject`, `Shiboken.ObjectType`,
and legacy UI module objects. The output did not identify
`nana_sidecar.storage.workspace_lock`, `nana_sidecar.runtime_app` writer
handles, or the D3 owner lane as the root object.

## Boundary comparison

The strict D3 suite, including workspace lock, runtime authority, read models,
journey commands, journey runtime, and Claude adapter tests, passes 88 tests
with `-W error::ResourceWarning`. The D1/D2 non-UI groups also complete without
the shutdown warning when run independently. The warning is therefore
attributed to the pre-existing full-suite PySide6/legacy UI teardown graph,
outside the D3 write/lock/process path.

## Decision

F-18: **ACCEPT as an explicit non-blocking legacy teardown caveat**. It does
not authorize weakening D3 warning gates or claiming a general sandbox safety
property.

## 2026-08-16 recheck

The warning remains reproducible with the installed PySide6 6.11.1 and Python
3.12.13 using only:

```powershell
.\.venv\Scripts\python.exe -W always::ResourceWarning -c "import PySide6.QtCore"
```

That process emits `gc: 1 uncollectable objects at shutdown`; the application,
SQLite runtime and D3 services are not imported. Explicitly quitting and
deleting `QApplication` does not remove it. The warning is therefore retained
as an upstream legacy-runtime debt rather than hidden by a global warning
filter. D3 warning-as-error checks remain separate and strict.
