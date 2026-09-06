$ErrorActionPreference = 'Continue'
$taskCommands = 'python','py','uv','git','wsl','docker','nvidia-smi','clinfo','rocminfo','xrt-smi','xbutil','benchmark_app','verilator','iverilog','yosys','sbt','java','cmake','ninja','conda','xclbinutil','v++','aiecompiler','clang','cl'
$taskEnvironment = [ordered]@{
    collected_utc = [DateTime]::UtcNow.ToString('o')
    scope = 'PATH, PnP, known software directories and conda environment registry; no whole-machine absence claim'
    cpu = @(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors)
    video = @(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion)
    npu = @(Get-CimInstance Win32_PnPEntity | Where-Object {$_.Name -match 'AMD IPU Device|Neural Processing|AI Boost|NPU'} | Select-Object Name,Status,PNPClass,DeviceID)
    npu_driver = @(Get-CimInstance Win32_PnPSignedDriver | Where-Object {$_.DeviceName -eq 'AMD IPU Device'} | Select-Object DeviceName,DriverVersion,DriverDate,InfName)
    commands = @($taskCommands | ForEach-Object { $taskCmd = Get-Command $_ -ErrorAction SilentlyContinue; [ordered]@{ name = $_; source = @($taskCmd.Source); found = [bool]$taskCmd } })
    known_sdk_roots = @('D:\riallto\ipu_stack_rel_silicon_prod','D:\riallto\ipu_stack_rel_silicon_1.0','C:\RyzenAI','C:\Program Files\RyzenAI','C:\Xilinx','C:\Program Files\Xilinx','D:\Xilinx' | ForEach-Object { [ordered]@{path=$_;exists=(Test-Path -LiteralPath $_)} })
    conda_environments = @()
    driver_artifacts = @()
    power_scheme = @(powercfg /getactivescheme)
}
$taskCondaRegistry = 'C:\Users\72449\.conda\environments.txt'
if (Test-Path -LiteralPath $taskCondaRegistry) { $taskEnvironment.conda_environments = @(Get-Content -LiteralPath $taskCondaRegistry) }
$taskArtifacts = 'xbutil.exe','xrt_core.dll','xrt_coreutil.dll','amd_xrt_core.dll','onnxruntime.dll','onnxruntime_vitisai_ep.dll','validate_phx.xclbin','DPU_Sequence\df_bw_dpu.txt','aieml_gemm_vm_phx_4x4_bf16.xclbin','aieml_gemm_vm_phx_4x4_bf16.json'
$taskEnvironment.driver_artifacts = @($taskArtifacts | ForEach-Object { $taskPath = Join-Path 'C:\Windows\System32\AMD' $_; if (Test-Path -LiteralPath $taskPath) { $taskInfo = Get-Item -LiteralPath $taskPath; [ordered]@{path=$taskPath;size=$taskInfo.Length;sha256=(Get-FileHash -LiteralPath $taskPath -Algorithm SHA256).Hash.ToLower();file_version=$taskInfo.VersionInfo.FileVersion} } })
$taskEnvironment | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'evidence\host_inventory.json') -Encoding utf8
$taskEnvironment | ConvertTo-Json -Depth 7
