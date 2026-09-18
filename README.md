# 七目相机与 IMU 仿真 — Step 2

当前完成 Step 2：固定布局下逐相机 ideal/body/worn 有效像素遮挡与部件归因。21 张真实原生 RGB、独立 RTX 实例标签和全分辨率解析射线结果已保存。配置与第一步产物保持不变。

优先查看 [第二步报告](reports/step2/step2_report.md)、[C6 三模式对比](outputs/step2/comparisons/C6_three_modes.png)、[C3 遮挡来源](outputs/step2/worn/C3_sources_overlay.png)；全部七张对比图在 `outputs/step2/comparisons/`。

```powershell
# 校验现有产物并重新生成对照图/差异表
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_step2.ps1
# 全分辨率解析重算 + 已有 GPU 环境真实渲染/回传
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_step2.ps1 -Reanalyze -Render
```

远端复用第一步目录和 Isaac 环境；先逐字节核对冻结输入，仅上传第二步代码和分析选项。密码交互输入，不保存。不含安装或升级系统环境操作。公开克隆缺少的私有原件哈希检查会跳过并在 `frozen_after.json` 列出；本轮本机所有原件均已检查。解析统计属于当前未实测的结构占位模型，不能解释为联合空间覆盖率、硬件验收或七路并行性能。

以下保留第一步说明，第一步重建命令仅用于明确重跑第一步，不应作为第二步入口。

---

# 七目头戴相机与 IMU — Step 1

当前状态：**Step 1 已完成真实静态渲染与投影检查**。活动版本 `SIM-V0.2-vfov130`；原始包保持不变。

公开仓库包含必要的仿真模型、工作代码、场景和实际运行结果。客户原始PDF、组成图、原始图纸/CAD、完整ZIP及其审阅副本留在本地，不随仓库发布。缺少这些不公开的原件时，离线测试仅将对应原件哈希检查标记为跳过，仍验证全部随仓库交付的基线资产。

首次克隆后，在项目目录创建本机配置和隔离Python环境：

```powershell
uv venv --python 3.10 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-dev.txt
Copy-Item config/environment.example.json config/environment.local.json
```

离线运行可直接使用模板中的本机Python路径；远端渲染前编辑本机配置，填写已有GPU服务器和Isaac环境路径。密码只在连接时输入，不写入配置。当前适配和渲染验证仅针对Isaac Sim 6.0.1.0。

优先查看：

- [七路图像总览](outputs/step1/seven_camera_preview.png)
- [佩戴状态与相机位置/方向](outputs/step1/worn_overview.png)
- [角度检查预览](outputs/step1/angle_checks_preview.png)
- [完整报告](reports/step1_report.md)

Isaac 中打开 `scenes/inspection_scene.usda` 查看原始设备、佩戴占位和检查环境；查看 `scenes/worn_overview.usda` 并选 `/World/OverviewCamera` 可复现外部观察角度。C0–C6 位于 `/World/Rig/Sensors/`。所有资产引用是相对路径，应保持工程目录完整。通用 USD 查看器不保证支持鱼眼渲染。

重新派生配置和运行离线检查：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_step1.ps1
```

上传本工程、在已配置 GPU 服务器渲染并回传结果（密码仅交互输入，不保存）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_step1.ps1 -Render
```

本地开发依赖位于项目 `.venv`，由 `requirements-dev.txt` 记录。安装路径和远程连接信息集中在 `config/environment.local.json`；换电脑时调整其中 local_python。远端复用 `/root/autodl-tmp/envs/isaacsim-clean/bin/python` 的 Isaac Sim 6.0.1.0。启动脚本不会安装或升级 Isaac、驱动、CUDA 或 ROS。`ExecutionPolicy Bypass` 仅针对该 PowerShell 进程。

活动配置唯一来源：`config/rig_sim_v0.2.json`。`scripts/build_step1.py` 派生外参/内参与 USD 覆盖层；`src/rig_common.py` 复用并修正原包逻辑；`scripts/isaac_step1.py` 负责真实渲染；`scripts/finalize_step1.py` 检查回传产物并生成预览。

原生图像、有效掩膜和逐图元数据在 `outputs/step1/ideal/`；角度数据在 `angle_results.json/csv`，全尺寸靶标图片在 `angles/`。黑色无效区不代表结构遮挡。只有静态顺序采集经过验证，不代表七路并行30 FPS、硬件同步、IMU采样或SLAM通过。本轮在此停止。
