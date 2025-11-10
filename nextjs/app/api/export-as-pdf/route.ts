import path from "path";
import fs from "fs";
import puppeteer from "puppeteer";
import { v4 as uuidv4 } from 'uuid';
import { sanitizeFilename } from "@/app/(presentation-generator)/utils/others";
import { NextResponse, NextRequest } from "next/server";

export async function POST(req: NextRequest) {
  const { id, title } = await req.json();
  if (!id) {
    return NextResponse.json(
      { error: "Missing Presentation ID" },
      { status: 400 }
    );
  }
  const sessionId = getSessionId(req);
  const browser = await puppeteer.launch({
    executablePath: process.env.NEXT_PUBLIC_PUPPETEER_EXECUTABLE_PATH,
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--disable-web-security",
      "--disable-background-timer-throttling",
      "--disable-backgrounding-occluded-windows",
      "--disable-renderer-backgrounding",
      "--disable-features=TranslateUI",
      "--disable-ipc-flooding-protection",
    ],
  });
  const page = await browser.newPage();
  if (sessionId) {
    await page.setCookie({
      name: 'user_session',
      value: sessionId,
      domain: 'localhost',
      path: '/',
      httpOnly: true,
      secure: false,
    });
  }
  await page.setViewport({ width: 1280, height: 720 });
  page.setDefaultNavigationTimeout(300000);
  page.setDefaultTimeout(300000);

  await page.goto(`http://localhost:9205/pdf-maker?id=${id}`, {
    waitUntil: "networkidle0",
    timeout: 1200000,
  });

  await page.waitForFunction('() => document.readyState === "complete"');

  try {
    await page.waitForFunction(
      `
      () => {
        const allElements = document.querySelectorAll('*');
        let loadedElements = 0;
        let totalElements = allElements.length;
        
        for (let el of allElements) {
            const style = window.getComputedStyle(el);
            const isVisible = style.display !== 'none' && 
                            style.visibility !== 'hidden' && 
                            style.opacity !== '0';
            
            if (isVisible && el.offsetWidth > 0 && el.offsetHeight > 0) {
                loadedElements++;
            }
        }
        
        return (loadedElements / totalElements) >= 0.99;
      }
      `,
      { timeout: 300000 }
    );

    await new Promise((resolve) => setTimeout(resolve, 1000));
  } catch (error) {
    console.log("Warning: Some content may not have loaded completely:", error);
  }

  const pdfBuffer = await page.pdf({
    width: "1280px",
    height: "720px",
    printBackground: true,
    margin: { top: 0, right: 0, bottom: 0, left: 0 },
  });

  browser.close();

  const pdfFileName = `${uuidv4()}.pdf`;
  // const sanitizedTitle = sanitizeFilename(title ?? "presentation");
  const destinationPath = path.join(
    process.env.NEXT_PUBLIC_APP_DATA_DIRECTORY!,
    "exports",
    pdfFileName
  );
  await fs.promises.mkdir(path.dirname(destinationPath), { recursive: true });
  await fs.promises.writeFile(destinationPath, pdfBuffer);

  return NextResponse.json({
    success: true,
    path: destinationPath,
  });
}

// 添加一个新函数来获取 session_id
function getSessionId(request: NextRequest): string | null {
  // 尝试从 cookie 中获取 session_id
  const cookies = request.headers.get("cookie");
  if (cookies) {
    const sessionMatch = cookies.match(/user_session=([^;]+)/);
    if (sessionMatch && sessionMatch[1]) {
      return sessionMatch[1];
    }
  }
  
  // 尝试从 Authorization 头中获取
  const authHeader = request.headers.get("authorization");
  if (authHeader) {
    return authHeader.replace("Bearer ", "");
  }
  
  // 最后尝试从查询参数中获取
  return request.nextUrl.searchParams.get("user_session");
}
