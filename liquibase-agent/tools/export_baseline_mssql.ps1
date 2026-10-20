# Schema-only export (SQL Server) used as --baseline. Requires the SqlServer PowerShell module (offline install supported).
# Usage: .\export_baseline_mssql.ps1 -Server SQL01 -Database AppDb -Out baseline.sql
param([string]$Server, [string]$Database, [string]$Out = "baseline.sql")
Import-Module SqlServer
$srv = New-Object Microsoft.SqlServer.Management.Smo.Server $Server
$db  = $srv.Databases[$Database]
$opt = New-Object Microsoft.SqlServer.Management.Smo.ScriptingOptions
$opt.DriAll = $true; $opt.Indexes = $true; $opt.Triggers = $true; $opt.IncludeIfNotExists = $false
$objs = @($db.Tables + $db.Views + $db.StoredProcedures + $db.UserDefinedFunctions) | Where-Object { -not $_.IsSystemObject }
$objs | ForEach-Object { $_.Script($opt); "GO" } | Out-File -Encoding utf8 $Out
