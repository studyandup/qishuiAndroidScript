# 汽水音乐 Android 自动化脚本

基于 [AScript](https://www.ascript.cn) 框架的 **Android 端**自动化脚本，自动观看汽水音乐的激励视频广告，领取免费听歌时长。

> 本项目参考 [qishuiAScriptProject](https://github.com/wei6718189/qishuiAScriptProject)（iOS 版）的思路，
> 完整重写为 Android 版本。原项目基于 `ascript.ios.*` + WebDriverAgent，
> 本项目基于 `ascript.android.*` + 无障碍服务，**免 Root、免越狱、无需外接 HID 硬件**。

## 功能特性

- 自动启动汽水音乐 App
- 自动点击「去看视频 领取时长」进入激励视频广告
- 自动等待广告倒计时结束（兼容多种倒计时文案格式）
- 自动处理广告中途弹出的「继续观看」弹窗
- 自动点击「领取成功」→「领取奖励」，完成一轮领取
- **循环领取直到今日额度用满**（识别到「明日免费听」自动停止）
- 全程 PaddleOCR V5 文字识别 + 固定坐标，无需依赖控件树

## 为什么用 OCR 而不是控件树

汽水音乐 Android 版是 **Flutter 自绘 UI**，`uiautomator dump` 只能抓到底部导航栏，
页面主体内容（按钮文字、广告倒计时）在控件树里完全读不到：

```
FrameLayout  id=navigation_tab_explore  [0,2430][240,2574]
TextView     text='发现'
FrameLayout  id=navigation_tab_commerce_reward  [720,2430][960,2574]
TextView     text='领时长'
...  # 页面内容一个都抓不到
```

所以本项目与原 iOS 版一致，采用 **OCR 识别文字 + 百分比/固定坐标点击** 的方案。

## 技术栈

| 模块 | 用途 |
| --- | --- |
| `ascript.android.system.open` | 启动 App |
| `ascript.android.action` | 点击、返回键等动作 |
| `ascript.android.screen.Ocr` | 文字识别（PaddleOCR V5 / MLKit） |

## 运行环境

- **平台**：Android（实测小米 14 / Android 16 / HyperOS 3.0）
- **AScript 版本**：支持 `ascript.android.*` 命名空间的版本
- **运行模式**：无障碍模式（无障碍 + 悬浮窗 + 图色权限）
- **OCR 引擎**：PaddleOCR V5（`Ocr.MODE_PADDLE_V5`）
- **Root**：不需要

## 快速开始

### 1. 安装 AScript

从官网下载安装 [AScript](https://www.ascript.cn/docs/android/download/)（选 64 位 APK）。

### 2. 开启权限

打开 AScript，确认以下三项都是「已授权 / 已开启」：

- 无障碍权限
- 悬浮窗权限
- 图色权限

建议同时把 AScript 的省电策略设为「无限制」，避免运行中被系统杀掉。

### 3. 安装本脚本

把本仓库整个目录放到手机的这个路径下：

```
/storage/emulated/0/airscript/model/qishui_ling_shichang/
```

目录结构必须是：

```
qishui_ling_shichang/
├── __init__.py      # 脚本入口（AScript 工程约定，必须叫这个名字）
├── build.as         # 工程配置
└── res/
    └── img/
        └── logo.png
```

也可以用 AScript 的 Web IDE（浏览器打开 `http://手机IP:9096`）新建同名工程后覆盖 `__init__.py`。

### 4. 运行

手机上打开 AScript → 小程序列表 → 点 `qishui_ling_shichang` 即可。

## 脚本流程

```
启动汽水音乐
    ↓
判断当前状态（OCR 识别屏幕文字）
    ├─ 领时长页     → 点「去看视频 领取时长」
    ├─ 广告播放中   → 等倒计时结束
    ├─ 继续观看弹窗 → 点「继续观看」恢复播放
    ├─ 领取成功     → 点右上角「领取成功」
    └─ 领取奖励弹窗 → 点「领取奖励」进入下一轮
    ↓
成功次数 +1，回到状态判断继续循环
    ↓
识别到「明日免费听」→ 今日额度已满 → 自动停止
    ↓
或连续 3 轮无进展 → 自动停止（兜底）
```

## 关键配置

修改 `__init__.py` 顶部常量：

| 常量 | 默认值 | 说明 |
| --- | --- | --- |
| `PKG` | `"com.luna.music"` | 汽水音乐包名 |
| `MAX_ROUNDS` | `60` | 最多领取轮数（防死循环） |
| `AD_TIMEOUT` | `120` | 单条广告最长等待秒数 |
| `IDLE_LIMIT` | `3` | 连续失败几次后停止 |

## 坐标标定

坐标基于 **1200×2670**（小米 14）实测。换其他机型需重新标定：

| 元素 | 坐标 | 说明 |
| --- | --- | --- |
| `XY_ENTRY` | (599, 1891) | 「去看视频 领取时长」入口 |
| `XY_CLAIM_OK` | (984, 181) | 广告右上角「领取成功」 |
| `XY_CLAIM_REWARD` | (599, 1458) | 弹窗「领取奖励」 |
| `XY_TAB_REWARD` | (840, 2500) | 底部「领时长」tab |

标定方法：在 AScript 里用 `Ocr.paddleocr()` 打印当前屏幕所有文字及其 `center_x/center_y`。

## 踩过的坑

实现过程中遇到并修复了三个真实陷阱，值得记录：

### 1.「领取成功」文案一直存在，不能作为广告结束的依据

广告页右上角的「领取成功」按钮**从广告开始就存在**，只是倒计时没走完时点它无效。
如果脚本靠它判断，会在广告没播完时提前点击，导致领不到奖励。

**解法**：用倒计时文字判断。倒计时消失 + 连续两次确认，才允许点击。

### 2. 倒计时文案有两种格式

实测遇到两种：

```
03秒后可领取奖励     ← 格式 A
14s领取成功          ← 格式 B
```

只匹配格式 A 会把格式 B 误判为「广告已结束」。

**解法**：两种格式都识别，并排除 `14s领取成功` 这种数字与文字粘连的情况。

### 3. 广告中途会弹「继续观看」

广告播放过程中可能弹出：

```
        继续观看
        坚持退出
```

这是广告平台的挽留弹窗。如果误判成「领取奖励」弹窗并点击，
会点到「坚持退出」或位置错乱，导致广告中断。

**解法**：单独识别为 `AD_PAUSED` 状态，点「继续观看」恢复播放，**绝不点「坚持退出」**。

## 安全红线

脚本只点击白名单坐标，**绝不点击**以下元素：

- 「立即下载」「下载」「安装」—— 广告的下载诱导
- 「坚持退出」—— 广告挽留弹窗
- 「开通会员」「4.8元」—— 付费入口

## 注意事项

1. **每日额度有限**：汽水音乐每天可领取的听歌时长有上限，脚本识别到「明日免费听」会自动停止，不要反复空跑。
2. **广告内容多变**：广告来自第三方平台（红果短剧、家博会等），页面元素千变万化，所以策略是「靠倒计时判断结束 + 固定坐标点右上角」，而不是匹配广告内容。
3. **保持屏幕常亮**：建议关闭自动锁屏，或运行期间保持屏幕点亮。
4. **仅限个人学习使用**：请遵守汽水音乐的用户协议。

## 项目结构

```
qishuiAndroid/
├── __init__.py          # 脚本主入口（AScript 工程约定，必须叫这个名字）
├── build.as             # 工程配置（pip 依赖 / 图色管线）
├── res/
│   └── img/
│       └── logo.png     # 工程图标
├── docs/
│   └── troubleshooting.md   # 调试与标定指南
├── .vscode/
│   └── settings.json    # 项目配置（平台 / 设备地址）
├── .trae/
│   └── rules/
│       └── ascript.md   # AScript AI 编码规则
├── .gitignore
└── README.md
```

## 相关文档

- [AScript 官网](https://www.ascript.cn)
- [AScript Android 文档](https://www.ascript.cn/docs/android/intro/)
- [AScript 编码规则](./.trae/rules/ascript.md)
- [调试与标定指南](./docs/troubleshooting.md)

## License

MIT
