#!/bin/bash

# 部署管理脚本
# 用于管理 Django 应用的生产环境部署

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置变量
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
PID_FILE="/tmp/gunicorn.pid"
GUNICORN_CONF="$PROJECT_DIR/gunicorn.conf.py"
ASGI_APP="project_base.asgi:application"
LOG_DIR="$PROJECT_DIR/logs"

# 检查 PID 文件是否存在
check_pid() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    else
        return 1
    fi
}

# 打印带颜色的消息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查环境
check_env() {
    print_info "检查环境配置..."
    
    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        print_error "未找到 python3，请先安装 Python"
        exit 1
    fi
    
    # 检查依赖
    if [ ! -f "$PROJECT_DIR/requirements.txt" ]; then
        print_error "未找到 requirements.txt"
        exit 1
    fi
    
    # 检查 .env 文件
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        print_warn "未找到 .env 文件，将使用环境变量或默认配置"
    fi
    
    # 检查 gunicorn
    if ! command -v gunicorn &> /dev/null; then
        print_error "未找到 gunicorn，请先安装: pip install -r requirements.txt"
        exit 1
    fi
    
    # 检查配置文件
    if [ ! -f "$GUNICORN_CONF" ]; then
        print_error "未找到 gunicorn.conf.py"
        exit 1
    fi
    
    print_info "环境检查完成"
}

# 安装依赖
install_deps() {
    print_info "安装 Python 依赖..."
    cd "$PROJECT_DIR"
    pip install -r requirements.txt
    print_info "依赖安装完成"
}

# 运行数据库迁移
migrate() {
    print_info "运行数据库迁移..."
    cd "$PROJECT_DIR"
    python manage.py makemigrations
    python manage.py migrate
    print_info "数据库迁移完成"
}

# 收集静态文件
collectstatic() {
    print_info "收集静态文件..."
    cd "$PROJECT_DIR"
    python manage.py collectstatic --noinput
    print_info "静态文件收集完成"
}

# 初始化模块状态
init_modules() {
    print_info "初始化模块状态..."
    cd "$PROJECT_DIR"
    python manage.py expire_modules 2>/dev/null || print_warn "expire_modules 命令执行失败（可能未实现）"
}

# 检查端口是否被占用
check_port() {
    local port=${1:-10080}
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        lsof -ti:$port > /dev/null 2>&1
    else
        # Linux
        netstat -tlnp 2>/dev/null | grep -q ":$port " || lsof -ti:$port > /dev/null 2>&1
    fi
}

# 启动服务
start() {
    print_info "启动服务..."
    
    # 如果端口被占用，尝试停止旧进程
    if check_port 10080; then
        print_warn "检测到端口 10080 被占用，尝试停止旧进程..."
        stop 2>/dev/null || true
        sleep 1
    fi
    
    if check_pid; then
        print_warn "服务已在运行中 (PID: $PID)"
        return 1
    fi
    
    # 再次检查端口（防止停止失败）
    if check_port 10080; then
        print_error "端口 10080 仍被占用，请手动停止占用该端口的进程"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            lsof -ti:10080 | xargs ps -p 2>/dev/null || true
        else
            netstat -tlnp 2>/dev/null | grep ":10080 " || true
        fi
        exit 1
    fi
    
    cd "$PROJECT_DIR"
    
    # 检查环境
    check_env
    
    # 收集静态文件
    collectstatic
    
    # 启动 Gunicorn（使用 nohup 确保后台运行）
    print_info "启动 Gunicorn..."
    
    # 确保 PID 文件目录存在
    mkdir -p "$(dirname "$PID_FILE")"
    
    # 启动 Gunicorn，等待 PID 文件创建
    nohup gunicorn "$ASGI_APP" -c "$GUNICORN_CONF" > /dev/null 2>&1 &
    local gunicorn_pid=$!
    
    # 等待 PID 文件创建（最多等待 5 秒）
    local wait_count=0
    while [ ! -f "$PID_FILE" ] && [ $wait_count -lt 10 ]; do
        sleep 0.5
        wait_count=$((wait_count + 1))
    done
    
    # 如果 PID 文件存在，读取实际的 master PID
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        # 验证进程确实在运行
        if ps -p "$PID" > /dev/null 2>&1; then
            print_info "服务启动成功 (PID: $PID)"
            return 0
        else
            rm -f "$PID_FILE"
            print_error "进程启动后立即退出，请检查日志: $LOG_DIR/gunicorn_error.log"
            exit 1
        fi
    else
        # PID 文件未创建，检查进程是否还在运行
        if ps -p "$gunicorn_pid" > /dev/null 2>&1; then
            print_warn "PID 文件未创建，但进程仍在运行 (PID: $gunicorn_pid)"
            echo "$gunicorn_pid" > "$PID_FILE"
            PID=$gunicorn_pid
            print_info "服务启动成功 (PID: $PID)"
            return 0
        else
            print_error "服务启动失败，请检查日志: $LOG_DIR/gunicorn_error.log"
            exit 1
        fi
    fi
}

# 停止服务
stop() {
    print_info "停止服务..."
    
    local pid_to_stop=""
    
    # 首先尝试从 PID 文件读取
    if check_pid; then
        pid_to_stop=$PID
    else
        # PID 文件不存在，尝试通过端口查找进程
        if check_port 10080; then
            if [[ "$OSTYPE" == "darwin"* ]]; then
                pid_to_stop=$(lsof -ti:10080 | head -n 1)
            else
                pid_to_stop=$(netstat -tlnp 2>/dev/null | grep ":10080 " | awk '{print $7}' | cut -d'/' -f1 | head -n 1)
            fi
            
            if [ -n "$pid_to_stop" ] && ps -p "$pid_to_stop" > /dev/null 2>&1; then
                print_warn "通过端口找到运行中的进程 (PID: $pid_to_stop)"
            else
                print_warn "服务未运行"
                return 1
            fi
        else
            print_warn "服务未运行"
            return 1
        fi
    fi
    
    if [ -z "$pid_to_stop" ]; then
        print_warn "服务未运行"
        return 1
    fi
    
    print_info "正在停止进程 $pid_to_stop..."
    kill "$pid_to_stop" 2>/dev/null || print_error "无法停止进程 $pid_to_stop"
    
    # 等待进程结束
    for i in {1..10}; do
        if ! ps -p "$pid_to_stop" > /dev/null 2>&1; then
            rm -f "$PID_FILE"
            print_info "服务已停止"
            return 0
        fi
        sleep 1
    done
    
    # 如果还没停止，强制杀死
    if ps -p "$pid_to_stop" > /dev/null 2>&1; then
        print_warn "强制停止进程 $pid_to_stop..."
        kill -9 "$pid_to_stop" 2>/dev/null || true
        rm -f "$PID_FILE"
        print_info "服务已强制停止"
    fi
}

# 重启服务
restart() {
    print_info "重启服务..."
    stop
    sleep 2
    start
}

# 查看服务状态
status() {
    print_info "检查服务状态..."
    
    if check_pid; then
        print_info "服务正在运行"
        echo "  PID: $PID"
        echo "  进程信息:"
        # macOS 和 Linux 的 ps 命令语法不同，需要适配
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            ps -p "$PID" -o pid,ppid,command,etime,stat 2>/dev/null || ps -p "$PID" -o pid,ppid,etime,stat 2>/dev/null
        else
            # Linux
            ps -p "$PID" -o pid,ppid,cmd,etime,stat 2>/dev/null || ps -p "$PID" -o pid,ppid,etime,stat 2>/dev/null
        fi
        echo ""
        echo "  监听端口:"
        # macOS 使用 lsof，Linux 使用 netstat
        if [[ "$OSTYPE" == "darwin"* ]]; then
            lsof -p "$PID" 2>/dev/null | grep LISTEN || print_warn "无法获取端口信息"
        else
            netstat -tlnp 2>/dev/null | grep "$PID" || lsof -p "$PID" 2>/dev/null | grep LISTEN || print_warn "无法获取端口信息"
        fi
    else
        print_warn "服务未运行"
    fi
}

# 查看日志
logs() {
    local lines=${1:-50}
    print_info "显示最近 $lines 行日志..."
    
    if [ -f "$LOG_DIR/gunicorn_error.log" ]; then
        echo ""
        echo "=== Gunicorn 错误日志 ==="
        tail -n "$lines" "$LOG_DIR/gunicorn_error.log"
    fi
    
    if [ -f "$LOG_DIR/gunicorn_access.log" ]; then
        echo ""
        echo "=== Gunicorn 访问日志 ==="
        tail -n "$lines" "$LOG_DIR/gunicorn_access.log"
    fi
    
    if [ -f "$LOG_DIR/django.log" ]; then
        echo ""
        echo "=== Django 日志 ==="
        tail -n "$lines" "$LOG_DIR/django.log"
    fi
    
    if [ -f "$LOG_DIR/platform_app.log" ]; then
        echo ""
        echo "=== 应用日志 ==="
        tail -n "$lines" "$LOG_DIR/platform_app.log"
    fi
}

# 实时查看日志
logs_follow() {
    print_info "实时查看日志（按 Ctrl+C 退出）..."
    
    if [ -f "$LOG_DIR/gunicorn_error.log" ] && [ -f "$LOG_DIR/gunicorn_access.log" ]; then
        tail -f "$LOG_DIR/gunicorn_error.log" "$LOG_DIR/gunicorn_access.log" "$LOG_DIR/django.log" "$LOG_DIR/platform_app.log" 2>/dev/null
    else
        print_error "日志文件不存在"
    fi
}

# 部署（完整流程）
deploy() {
    print_info "开始部署..."
    
    check_env
    install_deps
    migrate
    collectstatic
    init_modules
    
    if check_pid; then
        print_info "重启服务..."
        restart
    else
        print_info "启动服务..."
        start
    fi
    
    sleep 2
    status
    
    print_info "部署完成！"
}

# 显示帮助信息
show_help() {
    cat << EOF
部署管理脚本

用法: $0 <command> [options]

命令:
    start           启动服务
    stop            停止服务
    restart         重启服务
    status          查看服务状态
    deploy          完整部署（安装依赖、迁移、收集静态文件、启动服务）
    logs [lines]    查看日志（默认50行）
    logs-follow     实时查看日志
    migrate         运行数据库迁移
    collectstatic   收集静态文件
    install-deps    安装 Python 依赖
    check-env       检查环境配置
    help            显示此帮助信息

示例:
    $0 start                 # 启动服务
    $0 stop                  # 停止服务
    $0 restart               # 重启服务
    $0 status                # 查看状态
    $0 deploy                # 完整部署
    $0 logs 100              # 查看最近100行日志
    $0 logs-follow           # 实时查看日志

EOF
}

# 主函数
main() {
    case "${1:-help}" in
        start)
            start
            ;;
        stop)
            stop
            ;;
        restart)
            restart
            ;;
        status)
            status
            ;;
        deploy)
            deploy
            ;;
        logs)
            logs "${2:-50}"
            ;;
        logs-follow)
            logs_follow
            ;;
        migrate)
            migrate
            ;;
        collectstatic)
            collectstatic
            ;;
        install-deps)
            install_deps
            ;;
        check-env)
            check_env
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"

