"""Report only measured Step 2 results; no fabricated acceptance thresholds."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'outputs/step2'
s=json.loads((out/'camera_occlusion_summary.json').read_text());rows=s['rows'];r=json.loads((out/'rtx_comparison.json').read_text());geometry=json.loads((out/'geometry_verification.json').read_text());checks=json.loads((out/'label_projection_checks.json').read_text())
def row(cid,mode):return next(v for v in rows if v['camera_id']==cid and v['mode']==mode)
lines=['# Step 2：逐相机有效像素遮挡与独立 RTX 核对','','## 实际结果','',
'本轮已在既有 Isaac Sim 6.0.1.0 / RTX PRO 6000 Blackwell Server Edition 环境真实完成 21 次静态原生分辨率采集，并对同一 RenderProduct 的 RGB 与独立实例标签进行核对。全分辨率解析计算使用 stride=1。没有进入联合覆盖率、运动、IMU 采样或结构优化。','',
'前向 C0/C1/C2 在当前模型中没有设备或佩戴结构遮挡。四路环视均有设备自遮挡，加入头部与头带后遮挡增加；C6 总遮挡最大。光心均不在不透明实体内部，未移动相机、缩小结构或增加近裁剪距离。','',
'| 相机 | N_valid | body 自遮挡 | worn 总遮挡 | worn 新增像素 | 新增占比 |','| --- | ---: | ---: | ---: | ---: | ---: |']
for i in range(7):
 cid=f'C{i}';b=row(cid,'body');w=row(cid,'worn');lines.append(f'| {cid} | {w["N_valid"]} | {100*b["occlusion_pixel_ratio"]:.6f}% | {100*w["occlusion_pixel_ratio"]:.6f}% | {w["N_added"]} | {100*w["added_pixel_ratio"]:.6f}% |')
lines+=['','比例是 N_blocked/N_valid。C1/C2 的有效圆与矩形交集、C3–C6 的有效圆之外均不进入分母。新增集合严格使用 worn_blocked AND NOT body_blocked；不能用头带或头部贡献变化替代。ideal 为零、body 是 worn 的子集、所有最近命中贡献之和等于总遮挡，均已检查。','',
'## 主要部件与图像位置','',
'body 的最大贡献均为中央外壳 central_housing：每路环视 26,287 像素，占有效像素 3.63178%；C3/C4 在图像右侧，C5/C6 在左侧。右散热件 right_heatsink 使 C5/C6 额外出现 15,357 像素、2.12171% 的贡献，分别位于右上/右下区域，因此右侧相机自遮挡较大。','',
'worn 的最大来源是头部椭球 head_ellipsoid：上视 C3/C5 各 89,345 像素（12.34381%），位于画面上部靠内侧；下视 C4/C6 各 130,764 像素（18.06622%），位于画面下部靠内侧。头带集中在对应上/下圆周附近。镜筒、侧壳与 USB 线缆也逐部件统计，未排除相机自己的镜筒；当前自身镜筒在有效视场内没有最近命中。','',
'头部会挡住部分原本可见的线缆，改变首命中归属。这些归属变化不一定新增遮挡像素。完整 18 个部件的 ID、名称、分组、USD 路径、逐模式贡献、质心与包围框见 `components.json` 与 `camera_occlusion_summary.json`。图中同侧壳体的对称圆周小片可能有位于图心的统计质心，不意味着它实际遮住图心。','',
'## RTX 全像素比较','',
'实例标签由 RTX 独立生成，非 RGB 差分，也不是把解析掩膜复制成标签。RGB 与 instance_segmentation 同一 RenderProduct、同分辨率、同相机投影、同场景 t=0。输入单位、相机位姿、0.0001 m 近裁剪及配置哈希核对通过。三模式仅改变 Housing、Accessories、WearerMount、Wearer 的可见性，环境与照明相同。','',
'| 相机/模式 | 解析遮挡像素 | RTX 遮挡像素 | RTX−解析 | IoU | 边界差异 | 非边界差异 |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
for v in r:
 if v['mask_IoU'] is not None:lines.append(f'| {v["camera_id"]}/{v["mode"]} | {v["analytic_blocked"]} | {v["rtx_blocked"]} | {v["area_delta_pixels"]} | {v["mask_IoU"]:.8f} | {v["boundary_disagreement"]} | {v["nonboundary_disagreement"]} |')
lines+=['','其余 13 个相机/模式组合两种掩膜均为空，IoU 记录 null，不人为填 1。边界带定义为两种遮挡掩膜边界并集向外膨胀 3 次（SciPy 默认四连通结构），限制在有效域；这是本轮工程诊断口径，不是客户指标。所有差异落在该带内；没有通过放宽视场或修改布局消除误差。差异图：绿色=共同遮挡、红色=仅解析、蓝色=仅 RTX、灰色=共同未遮挡、黑色=无效域。','',
f'7 项独立白色靶标注册检查均通过，含 C0 正前、C1 75°、C3 95°以及 C3/C4/C5/C6 105°。RGB/标签最大质心差 {max(x["centroid_difference_px"] for x in checks):.6f} px；标签相对理论投影最大残差 {max(x["label_projection_error_px"] for x in checks):.6f} px。2 px 仅为靶标注册工程检查阈值。由此确认实例标签在超过 90°的鱼眼区域没有退化为针孔投影。全像素掩膜比较已完成，非仅稀疏抽样验证。','',
'首次映射检查失败：Isaac 实例接口对个别 ID 返回空 idToLabels 路径，但 idToSemantics 保留唯一部件名（并转成小写）。修正为优先精确 USD 路径、空路径时使用本轮唯一语义名，随后完整重跑。未修改相机后端；原始实例数组、标签字典、首次失败记录与最终日志均保留。','',
'## 网格与解析几何','',
'先核对 18 个实际 USD Mesh 的分组、世界变换后 B 坐标顶点与解析表面，再进行比较。全部网格 doubleSided=true。顶点表面径向误差最大 0.0002123 mm；AABB 的最大差值是头部椭球 0.053275 mm。长方体边界只存在浮点误差，圆柱和椭球采用离散面片逼近，未修改网格以匹配统计。','',
'从形状中心向面片中心发射射线测得的最大内缩距离：镜筒约 0.00169 mm、线缆约 0.00644 mm、头部椭球约 0.608125 mm。这是面中心采样量，不是严格 Hausdorff 上界。RTX 的 worn 遮挡面积比解析少 127–229 像素，与网格离散边界差异一致；本轮未将每个边界像素强行归因为单一原因。像素采样、栅格边缘与有限网格分辨率仍影响边界。AA 设置为 0，但不宣称所有渲染采样效应消失。','',
'## 数据、验证与复现','',
'每个模式保存 7 张原始 RGB、有效域处理图和逐图元数据；`*_analytic.npz` 含 valid、blocked、first_hit_id、hit_distance_m、state、added_blocked。state=0/1/2 对应 INVALID/CLEAR/BLOCKED；无命中距离 NaN，单位 m，从解析内部 mm 仅转换一次。16 位 ID PNG 与彩色展示分开；`*_rtx.npz` 保留原始 renderer_instance_id 和映射部件 ID，标签 JSON 可追溯。环境、墙面、照明和无效圆外黑色都不算设备遮挡。','',
'距离与解析首命中来源是解析结果；RTX 核对遮挡面积和部件可见标签，不代表已验证逐像素射程。`rtx_comparison.json` 另列共同遮挡区的部件归属差异数和各部件 RTX 面积。此模型未实测，不代表真实鼻、耳、头发或肩臂；没有自行增强人体模型。','',
'执行入口：','',
'```powershell','powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_step2.ps1','powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_step2.ps1 -Reanalyze -Render','```','',
'本轮实际执行：本地 `analyze_step2.py`；已授权 SFTP 上传第二步代码；既有 Isaac Python 启动 `start_step2_job.py`；回传 Step 2 产物；本地 `finalize_step2.py`、`tests/test_step2.py` 以及 PowerShell 入口检查。没有运行会覆盖第一步的 build/isaac/finalize 脚本。','',
'5 项测试含多个几何与产物断言：已知盒体/椭球/圆柱命中及未命中、轴向与超过 90°射线、米制导出、无效像素排除、唯一最近命中、模式集合与贡献总和、冻结文件。结果在 `test_results.json`。全分辨率输出校验另外覆盖 21 个 RGB/标签尺寸、哈希与 t=0，以及 7 个投影注册用例。','',
f'活动配置 SHA-256：`{s["config_sha256"]}`。原始资料、第一步场景/报告/输出和活动配置的前后哈希在 `frozen_before.json` / `frozen_after.json`；本机全部核对未改变。未修改共享 `rig_common.py` 或 `projection.py`，因此无需改动或重生成第一步。Git 开始于 main 的参考提交 81cdea147b77dfbe8d40e5413d379c06fe139c1f，无用户工作区改动。','',
'## 优先查看','',
'- `outputs/step2/comparisons/C0_three_modes.png` 至 `C6_three_modes.png`：每相机三模式同尺度、保留宽高比。','- `outputs/step2/worn/C3_sources_overlay.png`、`C6_sources_overlay.png`：最大新增遮挡及部件名称。','- `outputs/step2/body/C5_sources_overlay.png`：右散热件影响。','- `outputs/step2/{mode}/C*_rtx_difference.png`：解析/RTX 差异。','- `outputs/step2/camera_occlusion_summary.csv` 与 `rtx_comparison.csv`：可复核数值。','',
'本轮没有执行阻断项。保留 legacy fisheyePolynomial 弃用警告，结果仅针对当前已验证环境。静态顺序采集不是七路并行 30 FPS、硬件同步、IMU 或 SLAM 验证；未设定遮挡小于某百分比的客户合格标准。完成本轮后停止，等待用户决定是否调整结构。']
(ROOT/'reports/step2/step2_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
