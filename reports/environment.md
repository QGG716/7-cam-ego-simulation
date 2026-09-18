# 实际执行环境 — 2026-09-18

## 本机
原生 Windows PowerShell，OS build 26200，注册表 DisplayVersion 25H2；不是WSL。WSL未安装。本机CIM查询被拒绝且PATH无nvidia-smi，所以本机GPU型号/显存/驱动保留UNKNOWN；全部渲染在已授权服务器执行。

本地项目 D:/code/7-cam-ego-simulation。最初缺包的环境报告已归档到 reports/preflight_initial。用户后续提供的SIM-V0.1包已安全解压，25个文件逐项SHA-256核对，原件未改写。客户PDF10页已提取阅读，重点第2/4/6/7页与4页布局图纸已视觉核对，组成图已查看。审阅副本在source_review/。

基础Python：C:/Users/liukai_xd/AppData/Roaming/uv/python/cpython-3.10-windows-x86_64-none/python.exe，3.10.21。项目内新建.venv，安装numpy 2.2.6、scipy 1.15.3、Pillow 12.3.0、PyMuPDF 1.28.2、Paramiko 5.0.0及必要依赖，未修改系统Python。

实际命令：
~~~powershell
uv --cache-dir .cache/uv venv --python C:/Users/liukai_xd/AppData/Roaming/uv/python/cpython-3.10-windows-x86_64-none/python.exe .venv
uv --cache-dir .cache/uv pip install --python .venv/Scripts/python.exe numpy scipy pillow pymupdf paramiko
~~~

## GPU服务器与实际启动入口
| 项目 | 实测 |
| --- | --- |
| SSH | 已授权服务器认证成功；具体连接信息仅保存在本机config/environment.local.json |
| 独立工程目录 | /root/autodl-tmp/7-cam-ego-simulation-step1 |
| OS | Ubuntu 22.04.5 LTS；Linux 5.15.0-78-generic x86_64 |
| GPU | NVIDIA RTX PRO 6000 Blackwell Server Edition |
| 显存 | 97887 MiB |
| 驱动 | 580.95.05 |
| CUDA显示 | nvidia-smi显示13.0；这是驱动报告值，非Toolkit验证 |
| Isaac Python | /root/autodl-tmp/envs/isaacsim-clean/bin/python，3.12.3 |
| Isaac | isaacsim / sensor / kernel / replicator 6.0.1.0 |
| 实际运行 | 上述Python → scripts/isaac_step1.py → SimulationApp → USD/Replicator RGB |
| 渲染 | RayTracedLighting，单GPU，静态顺序导出 |
| USD库 | 日志中pxr 0.25.11 |

系统/usr/bin/python3为3.10.12，未用于启动Isaac。服务器Isaac环境与Windows .venv独立，没有WSL路径或Python混用。

成功命令：
~~~bash
/root/autodl-tmp/envs/isaacsim-clean/bin/python /root/autodl-tmp/7-cam-ego-simulation-step1/scripts/start_remote_job.py --task all
~~~
启动脚本为本进程设置OMNI_KIT_ACCEPT_EULA=YES、OMNI_KIT_ALLOW_ROOT=1和工程.cache/runtime目录。最终完整运行日志isaac_all.log；任务已结束，无持续运行的渲染服务。

## 接口与文档核对
已阅读实际安装的extsDeprecated/isaacsim.sensors.camera/isaacsim/sensors/camera/camera.py中OpenCV设置器及_set_lens_distortion_properties，确认schema和属性命名。源码摘录在installed_projection_source.txt和installed_projection_setter.txt，安装盘点在remote_environment.json。

本轮以USD直接配置相机，复用Replicator，避免位姿API自动换轴。C0应用OmniLensDistortionOpenCvPinholeAPI；C1–C6保留legacy fisheyePolynomial，无新lens schema叠加。实际属性/schema/光心/朝向检查保存在outputs/step1/usd_runtime_verification.json。

已查阅[NVIDIA Isaac Sim 6.0相机文档](https://docs.isaacsim.omniverse.nvidia.com/6.0.0/sensors/isaacsim_sensors_camera.html)和[Omniverse相机文档](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/cameras.html)。官方文档说明原生OpenCV支持、旧属性可能被新schema覆盖，以及6.0 LUT回退针孔问题。本轮未启用LUT。安装目录未找到网页列出的standalone OpenCV示例，使用实际安装源码和真实角度靶标核对接口行为。

## 修复及范围
首次启动使用错误许可变量导致EOF，改为Kit实际使用的变量后成功。初始C3半径2.5 mm靶标太小，增大到6 mm（角半径约0.344°，不跨测试边界）后复测通过。总览环境父节点最初缺少Xform类型，显式声明后成功。失败日志及首轮图像保留，见isaac_bootstrap_attempt1.log、isaac_angles_initial_small_targets.log、isaac_overview_typename_failure.log及outputs/step1/diagnostics/。

按用户授权使用SSH/SFTP上传本工程必要代码、配置和模型并回传结果。未安装/升级服务器Isaac、驱动、CUDA或ROS，未修改其他工程，未开放端口或建立隧道。密码未存入项目；主机公钥记录于被忽略的.ssh/known_hosts。后续按用户明确指令发布到指定GitHub仓库；客户原件及连接配置不纳入公开提交。
