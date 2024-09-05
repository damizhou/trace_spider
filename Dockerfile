FROM ubuntu:24.04
MAINTAINER damifandocker
ADD .. /app
# 设置工作目录
WORKDIR /app

# 添加Deadsnakes PPA
RUN apt-get update && apt-get install -y software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa -y && \
    apt-get update

# 安装Python 3.9和其他工具
RUN apt-get install -y \
    vim \
    sudo \
    python3.9 \
    python3-pip \
    python3.9-venv \
    net-tools \
    wget \
    curl \
    python-is-python3 \
    ethtool \
    libpcap-dev \
    tcpdump
