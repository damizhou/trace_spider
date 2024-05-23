FROM debian:bullseye
MAINTAINER damifandocker
ADD .. /app
# 设置工作目录
WORKDIR /app

# 安装基本工具和依赖
RUN apt-get update && apt-get install -y \
    vim \
    sudo \
    python3.9 \
    python3-pip \
    python3.9-venv \
    net-tools \
    wget    \
    curl    \
    python-is-python3 \
    ethtool \
    libpcap-dev \
    tcpdump

# 将vim设为默认编辑器
RUN update-alternatives --set editor /usr/bin/vim.basic

#ADD .. .
## 取消网卡合并包，需要在启动容器之后跑
## RUN sudo ethtool -K eth0 tso off gso off gro off
#RUN pip3 install --no-cache-dir -r requirements.txt
#
## 安装chrome浏览器和驱动已经相关依赖
#RUN sudo apt install -y \
#    fonts-liberation    \
#    libasound2  \
#    libatk-bridge2.0-0  \
#    libatk1.0-0 \
#    libatspi2.0-0   \
#    libcairo2   \
#    libcups2    \
#    libdrm2 \
#    libgbm1 \
#    libgtk-3-0  \
#    libnspr4    \
#    libnss3 \
#    libpango-1.0-0  \
#    libu2f-udev \
#    libvulkan1  \
#    libxcomposite1  \
#    libxdamage1 \
#    libxfixes3  \
#    libxkbcommon0   \
#    libxrandr2  \
#    xdg-utils   \
#    procps
#RUN sudo dpkg -i deployment/chrome124.0.6367.201/google-chrome-stable_current_amd64.deb
#RUN sudo apt install -f
#RUN sudo dpkg -i deployment/chrome124.0.6367.201/google-chrome-stable_current_amd64.deb
#RUN sudo mv deployment/chrome124.0.6367.201/chromedriver /usr/bin
#
#
## 默认命令，打开vim
#CMD ["bash"]
