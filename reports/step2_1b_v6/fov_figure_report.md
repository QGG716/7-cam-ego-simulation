# 七目相机新视场 - v6

本轮承接 v5（`2c382882dbace7dbca5b34468b61552b3aabfc51`）。活动配置已按用户最新要求修改，C2 与 C1 同步；在原有 GPU 环境完成七路原生 RGB 重新渲染，并导出总图 PNG / PDF / SVG 和 A/B/C/D 放大图。

| 相机 | H × V | 分辨率 | 投影 |
| --- | --- | --- | --- |
| C0 | 120° × 87° | 1920 × 1080 | 针孔，独立 fx/fy |
| C1 / C2 | 160° × 120° | 1600 × 1300 | 理想等距鱼眼，独立 fx/fy |
| C3 / C4 / C5 / C6 | 188° × 133° | 1080 × 960 | 理想等距鱼眼，独立 fx/fy |

[总图 PNG](../../outputs/step2_1b_v6/fov_overview_wearer_v6.png) · [PDF](../../outputs/step2_1b_v6/fov_overview_wearer_v6.pdf) · [SVG](../../outputs/step2_1b_v6/fov_overview_wearer_v6.svg) · [七路原图](../../outputs/step2_1b_v6/raw/) · [分区放大图](../../outputs/step2_1b_v6/panels/)

## 修改范围

A 区复用 v3 无帽人物、设备佩戴关系、外部截图和坐标方向；B 区 C1/C0/C2、C 区 C3/C5、D 区 C4/C6 均换成新视场的实际原生渲染。延续 v5 的原图版式，无重叠阴影、彩色区域、曝光增益或逐图调色。排版只等比例缩放完整画幅。人物、设备、佩戴位姿、相机/IMU 位置与朝向、图像分辨率均未改变。

活动输入仍为 `config/rig_sim_v0.2.json`，版本更新为 `SIM-V0.3-hv`；`active_scene` 和 `active_calibration` 指向本轮 v6 派生文件。新场景仅覆盖相机光学参数，继承 v3 场景。v3 的静态佩戴适配结论仅作为既有几何来源，未宣称本轮重新进行适配实验。

## H/V 与成像域假设

用户给出水平、垂直视场，未给出实测畸变或镜头像圈。在保留分辨率与等距角度关系的前提下，本轮采用独立横纵像素焦距及完整矩形成像域：

- 针孔：`fx=W/(2*tan(H/2))`、`fy=height/(2*tan(V/2))`。
- 鱼眼：`fx=W/radians(H)`、`fy=height/radians(V)`；归一化像素坐标的长度为离轴角 theta，射线为 `(sin(theta)*ax/theta, sin(theta)*ay/theta, cos(theta))`。
- H/V 定义在画幅的水平、垂直中心线上；像素中心为 `u+0.5, v+0.5`。
- 原有 220° 圆形有效域已由本轮 H188° × V133° 矩形域取代，不再沿用旧圆形掩膜。全部矩形像素是该仿真假设下的有效射线；暗色区域不能仅凭颜色判断为遮挡。
- 由矩形角点推导的最大离轴角分别为前向 100°、上下四目约 115.1445°，不是新增的客户镜头参数，也不是实测镜头标定。

新鱼眼通过 RTX 原生 LUT 相机发射与上述公式一致的射线。方向纹理按各传感器像素中心生成，逆映射纹理采用 2048 × 2048 八面体方向编码。两组 LUT 对应前向鱼眼和上下四目，EXR 往返读取保持 float32 数组一致。C0 使用原生 OpenCV pinhole 相机。未从旧图裁切、拉伸或做 RGB 重映射。

实现参考 [NVIDIA 原生相机与 LUT 文档](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/cameras.html)，采用其相机坐标和八面体编码 Z 方向约定。当前运行环境原生 OpenCV fisheye 路径在试验中裁掉超过 90° 的射线，因此本轮使用 LUT 执行同一等距数学投影。

## 验证与边界

- 数学检查：指定 H/V 中心线边界、边界外不可见、双向投影、完整矩形成像域、像素射线一致性、旧等距模型兼容性。
- 几何检查：与旧配置相比，全部几何参数、内布局、相机位置/朝向及分辨率一致。
- 派生检查：新标定、USD 相机层和渲染状态的活动配置 SHA-256 一致；四张 LUT 的哈希与清单一致。
- GPU 检查：七路实际 RGB 渲染通过，相机世界位置和朝向检查通过。上下四目共 138 个近身首交点与实际原生径向深度比对，最大误差约 0.101 mm，超过 5 mm 的样本为 0。前向三目此稀疏近身采样没有命中，不能据此声称已验证前向深度；该检查也不是全画幅光度或硬件标定验证。
- 图面检查：七幅全画幅等比例展示、无图内标注；PNG 与 PDF 已目视复核，PDF 为单页，新参数文字正确。图像和源文件哈希见 `delivery_validation.json`。
- 旧 Step 1/2 测试改为读取 `previous_rig_sim.json` 中的旧配置，继续验证对应历史产物及冻结哈希；新活动参数由 `test_optics_hv_v6.py` 单独验证，未改写旧渲染结果或旧报告。

仅验证本次静态成像与参数一致性，不新增覆盖率、结构优化、运动、同步、IMU 序列或 SLAM 结论。

## 复现

本地重建相机层和版式（使用已提交的原图）：

```powershell
.venv/Scripts/python.exe scripts/build_optics_v6.py
.venv/Scripts/python.exe scripts/build_fov_figure_v6.py
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

在已有授权 GPU 工程重建 LUT、重新渲染并回传（读取本机私有连接配置；密码仅交互输入）：

```powershell
.venv/Scripts/python.exe scripts/run_fov_figure_v6.py
```

GPU 复现入口依赖既有 v3 场景、NVIDIA Office/人物资产及缓存、既有 Isaac Sim 与 OpenCV EXR 支持；没有安装或升级系统组件。公开仓库仅提交工程自建 LUT、场景覆盖层及输出，不提交客户原始资料、NVIDIA 原始资产缓存或连接凭据。旧阶段的重渲染入口使用旧光学假设，复现历史阶段请使用其对应提交；不要让旧入口覆盖当前 v6 配置和历史结果。
