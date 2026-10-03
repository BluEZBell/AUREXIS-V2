@echo off
echo Running test...
for /f "tokens=1" %%a in ('echo foo^|findstr "foo"') do echo MATCH_ESCAPED: %%a
for /f "tokens=1" %%a in ('echo bar ^| findstr "bar"') do echo MATCH_ESCAPED_SPACE: %%a
for /f "tokens=1" %%a in ('echo baz ^| findstr "baz"') do echo MATCH_ESCAPED_BAZ: %%a
for /f "tokens=1" %%a in ('echo qux | findstr "qux"') do echo MATCH_UNESCAPED: %%a
