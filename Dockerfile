# docsort 容器镜像（信创服务器常用交付方式）
# 构建需在目标架构机器或开启 QEMU 的机器上执行:
#   ARM64(飞腾/鲲鹏): docker build -t docsort:1.0 .
#   运行:
#     docker run --rm -v /data/case:/data -v /data/output:/out docsort:1.0 \
#       run /data --config /app/rules.yaml --output-dir /out
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    || pip install --no-cache-dir -r requirements.txt \
       -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY docsort/ ./docsort/
COPY tests/ ./tests/
COPY rules.yaml ./

# 默认输出到容器内 /out，运行时用 -v 挂载到宿主机
ENTRYPOINT ["python", "-m", "docsort"]
CMD ["--help"]
