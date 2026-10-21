"""生成冒烟测试样例 PDF（用 PyMuPDF 写入文本层，模拟电子版文档）。"""
import shutil
from pathlib import Path

import fitz

HERE = Path(__file__).parent
SAMPLES = HERE / "samples"
if SAMPLES.exists():
    shutil.rmtree(SAMPLES)
SAMPLES.mkdir(parents=True)


def make_pdf(name: str, pages_text: list):
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        # fontname="china-s": 内置简体中文字体，否则中文无法写入文本层
        page.insert_textbox(fitz.Rect(50, 50, 545, 750), text,
                            fontsize=12, fontname="china-s")
    doc.save(SAMPLES / name)
    doc.close()


make_pdf("invoice_demo.pdf", [
    "增值税电子普通发票\n发票号码: 24312000000123456789\n开票日期: 2026年10月20日\n"
    "购买方: 某某科技有限公司\n货物名称: *信息技术服务*系统维护\n税率 6%  税额 283.02\n价税合计 5000.00 元",
])
make_pdf("contract_demo.pdf", [
    "劳动聘用合同\n甲方: 某某科技有限公司\n乙方: 张三\n"
] + [f"第{i}条 双方权利义务约定,本合同条款长期履行业务往来的具体内容说明。"
     for i in range(2, 51)])
make_pdf("unknown_demo.pdf", [
    "会议纪要\n时间: 2026年10月20日\n参加人员: 若干\n议题: 讨论季度工作安排与资源协调事项。",
])

print("样例已生成:", SAMPLES)
for p in sorted(SAMPLES.iterdir()):
    print(" -", p.name)
