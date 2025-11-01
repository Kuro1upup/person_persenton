from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from typing import Optional, Dict, Any
import os
from datetime import datetime, timedelta

# 导入用户配置相关的模块
from utils.user_config import get_user_config, update_env_with_user_config

from utils.get_env import get_jwt_token_secret_key_env

# 创建认证路由器
AUTH_ROUTER = APIRouter(prefix="/auth", tags=["Auth"])

# 获取JWT密钥
JWT_SECRET = get_jwt_token_secret_key_env()
JWT_ALGORITHM = "HS256"

# 支持的用户角色
available_roles = ["payment", "subscription", "card"]

# 模拟用户会话存储
USER_SESSIONS = {}

@AUTH_ROUTER.get("/")
async def auth_with_token(
    token: str, 
    request: Request,
    response: Response
):
    """
    验证来自compareGPT的JWT令牌并创建用户会话
    """
    try:
        # 验证JWT令牌
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        user_name: str = payload.get("user_name")
        role: str = payload.get("role")
        api_key: str = payload.get("api_key")
        
        # 验证所有必需字段
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token: missing user ID")
        if user_name is None:
            raise HTTPException(status_code=401, detail="Invalid token: missing user name")
        if role is None:
            raise HTTPException(status_code=401, detail="Invalid token: missing user role")
        if api_key is None:
            raise HTTPException(status_code=401, detail="Invalid token: missing API Key")
        
        # 验证角色是否有效
        if role == "free":
            raise HTTPException(status_code=401, detail=f"Invalid token: unsupported role '{role}'")
        
        # 为用户创建会话ID
        session_id = f"session_{user_id}_{datetime.now().timestamp()}"
        
        # 存储用户会话信息
        USER_SESSIONS[session_id] = {
            "user_id": user_id,
            "user_name": user_name,
            "role": role,
            "api_key": api_key,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(hours=12)
        }
        
        # 设置会话Cookie
        response.set_cookie(
            key="user_session",
            value=session_id,
            httponly=True,
            secure=False,  # 在生产环境中应设置为True
            samesite="lax",
            expires=(datetime.now() + timedelta(hours=12)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        )
        
        # 返回认证成功信息
        return {
            "message": "Authentication successful",
            "user_id": user_id,
            "user_name": user_name,
            "role": role,
            "session_id": session_id
        }
        
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

# 获取当前登录用户的依赖项 - 返回完整用户信息
def _get_current_user_details(request: Request) -> Optional[Dict[str, Any]]:
    """
    获取当前登录用户的完整信息（包含userId, userName, role等）
    """
    session_id = request.cookies.get("user_session")
    
    if not session_id or session_id not in USER_SESSIONS:
        return None
    
    session = USER_SESSIONS[session_id]
    
    # 检查会话是否过期
    if datetime.now() > session["expires_at"]:
        del USER_SESSIONS[session_id]
        return None
    
    # 返回用户详细信息（不包含apiKey）
    return session

# 获取当前登录用户的依赖项 - 仅返回用户ID
def get_current_user(request: Request) -> Optional[str]:
    """
    获取当前登录用户的ID（兼容现有代码）
    """
    user_details = _get_current_user_details(request)
    if user_details:
        return str(user_details["user_id"])
    return None

# 基于角色的权限控制依赖项
def get_user_with_model_access(request: Request) -> Dict[str, Any]:
    """
    获取当前登录用户信息，并验证是否有权限访问大模型接口
    subscription和card用户可以访问所有接口，payment用户只能访问不需要使用大模型的接口
    """
    user_details = _get_current_user_details(request)
    
    if not user_details:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # 检查用户角色是否有权限访问大模型接口
    if user_details["role"] == "payment":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account type does not have access to this feature"
        )
    
    return user_details

# 获取当前登录用户的API Key - 用于调用大模型接口
def get_current_api_key(request: Request) -> Optional[str]:
    """
    获取当前登录用户的API Key
    """
    user_details = _get_current_user_details(request)
    if user_details:
        return user_details["api_key"]
    return None

@AUTH_ROUTER.get("/user")
async def get_user_info(current_user: Optional[Dict[str, Any]] = Depends(_get_current_user_details)):
    """
    获取当前登录用户的信息
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # 这里可以从用户配置或数据库中获取更多用户信息
    user_config = get_user_config()
    
    return {
        "user_id": current_user["user_id"],
        "user_name": current_user["user_name"],
        "role": current_user["role"],
        "config": user_config.model_dump()
    }

@AUTH_ROUTER.post("/logout")
async def logout(request: Request, response: Response):
    """
    用户登出，清除会话
    """
    session_id = request.cookies.get("user_session")
    
    if session_id and session_id in USER_SESSIONS:
        del USER_SESSIONS[session_id]
    
    # 清除Cookie
    response.delete_cookie("user_session")
    
    return RedirectResponse(url="/")