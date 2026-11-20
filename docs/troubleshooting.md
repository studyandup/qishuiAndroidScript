# 调试与标定指南

本文档记录如何在本脚本基础上调试、以及换机型时如何重新标定坐标。

## 一、快速诊断环境

在 AScript 里执行以下代码，确认 API 可用：

```python
from ascript.android.screen import Ocr, capture
from ascript.android.system import open as app_open

Ocr.set_engine(Ocr.MODE_PADDLE_V5)
print("截图:", type(capture()).__name__)
print("OCR 命中:", Ocr.find("领取"))
```

正常输出类似：

```
截图: Bitmap
OCR 命中: {'confidence': 0.99, 'text': '领取', 'rect': [416, 1868, 782, 1912],
          'center_x': 599, 'center_y': 1890}
```

## 二、查看当前屏幕所有文字

标定坐标时最常用的代码：

```python
from ascript.android.screen import Ocr

Ocr.set_engine(Ocr.MODE_PADDLE_V5)
for t in (Ocr.paddleocr() or []):
    print("%r  (%s, %s)" % (t.text, t.center_x, t.center_y))
```

输出示例：

```
'去看视频 领取时长'  (599, 1890)
'领取成功'          (984, 181)
'领取奖励'          (599, 1458)
'03秒后可领取奖励'   (885, 181)
```

## 三、换机型如何标定

脚本顶部的四个坐标需要重新标定：

```python
XY_ENTRY = (599, 1891)          # 「去看视频 领取时长」
XY_CLAIM_OK = (984, 181)        # 右上角「领取成功」
XY_CLAIM_REWARD = (599, 1458)   # 弹窗「领取奖励」
XY_TAB_REWARD = (840, 2500)     # 底部「领时长」tab
```

**标定步骤：**

1. 手动把汽水音乐停在「领时长」页，执行上面的「查看当前屏幕所有文字」代码，
   找到 `去看视频 领取时长` 的坐标 → 填入 `XY_ENTRY`
2. 手动点进一个广告，等倒计时结束，找到 `领取成功` 的坐标 → 填入 `XY_CLAIM_OK`
3. 点「领取成功」后，在弹窗里找到 `领取奖励` 的坐标 → 填入 `XY_CLAIM_REWARD`
4. 底部导航 `领时长` 的坐标 → 填入 `XY_TAB_REWARD`

**注意**：不同分辨率下 `XY_CLAIM_OK`（右上角）变化最大，务必重新量。

## 四、常见问题

### Q1：脚本一直显示「未知状态」

屏幕文字和脚本预期的不一样。执行「查看当前屏幕所有文字」，把实际文案贴到
`detect_state()` 里补充判断分支。

### Q2：点「领取成功」没反应

可能是广告倒计时还没结束。检查 `ad_countdown()` 是否能识别当前广告的倒计时格式，
新格式加一条正则即可。

### Q3：脚本在广告页卡住

广告可能弹了「继续观看」或其它挽留弹窗。检查 `detect_state()` 里
`has_text(items, "继续观看")` 分支是否命中，必要时补充新的弹窗关键词。

### Q4：明明额度满了还在跑

脚本靠「明日免费听」判断额度是否已满。如果该文案变了，需要在
`claim_reward()` 里更新判断关键词。兜底机制是连续 3 轮无进展自动停止
（`IDLE_LIMIT`）。

### Q5：OCR 识别不到文字

- 确认 `Ocr.set_engine(Ocr.MODE_PADDLE_V5)` 已调用
- 确认图色权限已开启
- 可尝试换成 `Ocr.MODE_MLK`（MLKit）对比识别率

## 五、远程调试（可选）

AScript 启动后会在 `9096` 端口提供 HTTP 服务，可用 adb 端口转发后在电脑上调试：

```bash
adb forward tcp:19096 tcp:9096

# 设备状态
curl http://127.0.0.1:19096/api/status

# 在设备上执行 Python
curl -X POST http://127.0.0.1:19096/api/gp/eval \
     -d "code=print('hello')"
```

`/api/gp/eval` 会执行传入的 `code`，并把 `_result` 变量的值返回。
适合在不修改工程的情况下快速试探 API。
