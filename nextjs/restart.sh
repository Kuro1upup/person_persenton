#!/bin/bash

# 设置脚本在执行过程中若有任何错误立即退出
export -e

# 打印当前目录，用于调试
echo "当前目录: $(pwd)"

# 检查npm是否已安装
if ! command -v npm &> /dev/null
then
    echo "错误: npm 未安装，请先安装Node.js和npm"
    exit 1
fi

# 检查pm2是否已安装
if ! command -v pm2 &> /dev/null
then
    echo "警告: pm2 未安装，正在尝试安装..."
    npm install -g pm2
    if [ $? -ne 0 ]
    then
        echo "错误: 安装pm2失败，请手动安装后再运行此脚本"
        exit 1
    fi
fi

# 停止已经运行的项目
echo "停止当前运行的项目"
pm2 stop slides-frontend

# 构建项目
echo "正在构建项目..."
npm run build

# 检查构建是否成功
if [ $? -ne 0 ]
then
    echo "错误: 项目构建失败，请检查错误信息"
    exit 1
fi

# 使用pm2启动项目，指定端口为9203，名称为slides-frontend
echo "正在使用pm2启动项目..."
pm2 start "PORT=9205 npm start" --name slides-frontend

# 检查启动是否成功
if [ $? -eq 0 ]
then
    echo "项目启动成功！以下是当前pm2管理的应用列表："
pm2 list
    echo "
使用以下命令管理项目：
- 查看日志: pm2 logs slides-frontend
- 停止项目: pm2 stop slides-frontend
- 重启项目: pm2 restart slides-frontend
- 查看详情: pm2 show slides-frontend
"
else
    echo "错误: 项目启动失败，请检查错误信息"
    exit 1
fi
