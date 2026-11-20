# -*- coding: utf-8 -*-
"""
汽水音乐 · 自动领取听歌时长（Android / AScript 工程版）
=====================================================
用法：在 AScript 的「小程序列表」里点本工程即可运行，无需电脑。

流程：
  领时长页 →「去看视频 领取时长」→ 激励视频广告
    → 等倒计时结束 →「领取成功」→「领取奖励」→ 下一轮
  一直领到弹出「明日免费听」（今日额度已满）自动停止

技术：PaddleOCR V5 文字识别 + 固定坐标点击
     （汽水音乐是 Flutter 自绘 UI，控件树读不到页面内容）

安全红线：只点白名单坐标，绝不点「立即下载」「坚持退出」「开通会员」
"""

import re
import time

from ascript.android import action
from ascript.android.screen import Ocr
from ascript.android.system import open as app_open

# ==================== 配置区 ====================
PKG = "com.luna.music"

# 坐标基于 1200x2670（小米14），换机型需重新标定
XY_ENTRY = (599, 1891)          # 「去看视频 领取时长」入口按钮
XY_CLAIM_OK = (984, 181)        # 广告右上角「领取成功」
XY_CLAIM_REWARD = (599, 1458)   # 弹窗「领取奖励」
XY_TAB_REWARD = (840, 2500)     # 底部「领时长」tab

MAX_ROUNDS = 60        # 最多领多少次（防死循环）
AD_TIMEOUT = 120       # 单条广告最长等待秒数
IDLE_LIMIT = 3         # 连续失败几次就停

Ocr.set_engine(Ocr.MODE_PADDLE_V5)

TODAY_FULL = False
_logs = []


# ==================== 工具函数 ====================
def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    _logs.append(line)
    print(line)


def texts():
    """抓当前屏幕所有文字，返回 [{text,x,y}, ...]"""
    try:
        res = Ocr.paddleocr()
        out = []
        for t in (res or []):
            out.append({
                "text": getattr(t, "text", "") or "",
                "x": getattr(t, "center_x", 0),
                "y": getattr(t, "center_y", 0),
            })
        return out
    except Exception as e:
        log("OCR 异常: %s" % e)
        return []


def has_text(items, keyword):
    for it in items:
        if keyword in it["text"]:
            return True
    return False


def find_text(items, keyword):
    for it in items:
        if keyword in it["text"]:
            return it
    return None


def ad_countdown(items):
    """提取广告倒计时剩余秒数；没有倒计时返回 None
    兼容两种真实格式：
        '03秒后可领取奖励'  -> 3
        '14s领取成功'       -> 14
    """
    for it in items:
        txt = it["text"]
        m = re.search(r"(\d+)\s*秒后可领取奖励", txt)
        if m:
            return int(m.group(1))
        m = re.search(r"(\d+)\s*[sS]\s*领取成功", txt)
        if m:
            return int(m.group(1))
        m = re.search(r"^(\d+)\s*[sS]$", txt.strip())
        if m:
            return int(m.group(1))
    return None


def claim_button_ready(items):
    """「领取成功」是否真的可以点：存在该文案、无倒计时、且不是 '14s领取成功' 粘连形式"""
    found = False
    for it in items:
        txt = it["text"]
        if "领取成功" not in txt:
            continue
        if re.search(r"\d+\s*[sS]", txt):
            return False
        found = True
    if not found:
        return False
    if ad_countdown(items) is not None:
        return False
    return True


def detect_state(items):
    """判断当前所处阶段"""
    if has_text(items, "继续观看"):
        return "AD_PAUSED"
    if ad_countdown(items) is not None:
        return "AD_PLAYING"
    if has_text(items, "领取奖励"):
        return "REWARD_POPUP"
    if claim_button_ready(items):
        return "AD_DONE"
    if has_text(items, "去看视频") or has_text(items, "领取时长"):
        return "ENTRY_PAGE"
    if has_text(items, "今日畅听") or has_text(items, "免费畅听"):
        return "ENTRY_PAGE"
    return "UNKNOWN"


def safe_click(x, y, desc):
    log("  点击 [%s] -> (%d,%d)" % (desc, x, y))
    action.click(x, y)
    time.sleep(1.2)


def handle_continue_watch():
    """广告中途弹「继续观看」时点它恢复播放（绝不能点「坚持退出」）"""
    hit = find_text(texts(), "继续观看")
    if hit:
        log("  检测到「继续观看」弹窗，点它恢复广告")
        action.click(hit["x"], hit["y"])
        time.sleep(1.5)
        return True
    return False


def click_claim_ok():
    """点「领取成功」前连续两次确认，防止广告没播完就点"""
    for _ in range(2):
        if not claim_button_ready(texts()):
            log("  倒计时仍在或状态不符，拒绝点击「领取成功」")
            return False
        time.sleep(1.5)
    safe_click(XY_CLAIM_OK[0], XY_CLAIM_OK[1], "领取成功")
    time.sleep(2)
    return True


def claim_reward():
    """在领取弹窗里点「领取奖励」，并识别是否已是明日额度"""
    global TODAY_FULL
    items = texts()
    if has_text(items, "明日免费听") or has_text(items, "明日"):
        TODAY_FULL = True
        log("  ★ 弹窗显示「明日免费听」→ 今日额度已满")
    safe_click(XY_CLAIM_REWARD[0], XY_CLAIM_REWARD[1], "领取奖励")
    time.sleep(3)
    return True


def wait_ad_finish(timeout=AD_TIMEOUT):
    """等广告倒计时结束，返回 'DONE' / 'POPUP' / None"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        items = texts()
        if has_text(items, "继续观看"):
            handle_continue_watch()
            continue
        if has_text(items, "领取奖励") and ad_countdown(items) is None:
            return "POPUP"
        cd = ad_countdown(items)
        if cd is not None:
            log("  广告倒计时剩 %d 秒，继续等待" % cd)
            time.sleep(min(cd + 1, 8))
            continue
        if claim_button_ready(items):
            return "DONE"
        time.sleep(2)
    return None


def finish_ad_and_claim():
    """广告播完后的收尾：点领取成功 → 点领取奖励"""
    if click_claim_ok():
        items = texts()
        if has_text(items, "领取奖励"):
            return claim_reward()
    items = texts()
    if has_text(items, "领取奖励"):
        return claim_reward()
    return False


# ==================== 单轮流程 ====================
def run_round(round_no):
    log("-" * 40)
    log("第 %d 轮开始" % round_no)

    items = texts()
    state = detect_state(items)
    log("当前状态: %s" % state)

    if state == "AD_PAUSED":
        handle_continue_watch()
        res = wait_ad_finish()
        log("广告等待结果: %s" % res)
        return res in ("DONE", "POPUP") and finish_ad_and_claim()

    if state == "AD_PLAYING":
        res = wait_ad_finish()
        log("广告等待结果: %s" % res)
        return res in ("DONE", "POPUP") and finish_ad_and_claim()

    if state == "AD_DONE":
        return finish_ad_and_claim()

    if state == "REWARD_POPUP":
        return claim_reward()

    if state == "ENTRY_PAGE":
        entry = find_text(items, "去看视频")
        if entry:
            safe_click(entry["x"], entry["y"], "去看视频领取时长")
        else:
            safe_click(XY_ENTRY[0], XY_ENTRY[1], "去看视频(固定坐标)")
        time.sleep(5)
        res = wait_ad_finish()
        log("广告等待结果: %s" % res)
        return res in ("DONE", "POPUP") and finish_ad_and_claim()

    log("未知状态，屏幕文字如下：")
    for it in items[:12]:
        log("    %r (%d,%d)" % (it["text"], it["x"], it["y"]))
    return False


# ==================== 主流程 ====================
def main():
    log("=" * 50)
    log("汽水音乐 · 自动领时长 启动")

    try:
        app_open(PKG)
        time.sleep(4)
        log("已打开汽水音乐")
    except Exception as e:
        log("打开 App 失败: %s" % e)

    success = 0
    idle = 0
    for i in range(1, MAX_ROUNDS + 1):
        try:
            ok = run_round(i)
        except Exception as e:
            log("第 %d 轮异常: %s" % (i, e))
            ok = False

        if ok:
            success += 1
            idle = 0
            log("✅ 第 %d 轮成功，累计 %d 次" % (i, success))
        else:
            idle += 1
            log("❌ 第 %d 轮未成功（连续 %d 次）" % (i, idle))

        if TODAY_FULL:
            log("★ 今日额度已满，停止")
            break
        if idle >= IDLE_LIMIT:
            log("连续 %d 轮无进展，停止（可能额度已满或界面异常）" % idle)
            break
        time.sleep(2)

    log("=" * 50)
    log("结束：成功领取 %d 次" % success)
    if TODAY_FULL:
        log("今日听歌时长额度已领满 🎉")


try:
    main()
except Exception:
    import traceback
    log("脚本异常：\n" + traceback.format_exc())

_result = "\n".join(_logs) if _logs else "no logs"
