import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import yt_dlp
import edge_tts
from google import genai

# --- Render Port Binding အတွက် Web Server ငယ်တစ်ခု ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

# Background တွင် Web Server ကို စတင်ရန်
threading.Thread(target=run_web_server, daemon=True).start()
# --------------------------------------------------

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"):
        await update.message.reply_text("ကျေးဇူးပြု၍ YouTube သို့မဟုတ် TikTok ဗီဒီယို လင့်ခ် (Link) တစ်ခု ပို့ပေးပါ။")
        return
        
    await update.message.reply_text("⏳ ဗီဒီယိုကို စတင် ဒေါင်းလုဒ်ဆွဲနေပါပြီ...")
    
    input_file = "input.mp4"
    output_file = "output.mp4"
    audio_file = "audio.mp3"
    
    try:
        ydl_opts = {'format': 'mp4', 'outtmpl': input_file}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        await update.message.reply_text("🤖 Gemini AI ဖြင့် ဗီဒီယိုကို လေ့လာပြီး မြန်မာ Recap ရေးနေပါပြီ...")
        
        uploaded_file = client.files.upload(file=input_file)
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=[uploaded_file, "Watch this video and write an engaging TikTok video recap script in natural Myanmar language. Return only the script text."]
        )
        script_text = response.text
        
        await update.message.reply_text(f"📝 ထွက်လာသည့် မြန်မာ Script:\n{script_text[:300]}...")
        
        await update.message.reply_text("🎙️ မြန်မာအသံဖိုင် ဖန်တီးနေသည်...")
        communicate = edge_tts.Communicate(script_text, "my-MM-ThihaNeural")
        await communicate.save(audio_file)
        
        await update.message.reply_text("🎬 TikTok Copyright မမိအောင် ဗီဒီယို ပြင်ဆင်နေသည်...")
        cmd = [
            'ffmpeg', '-y',
            '-i', input_file,
            '-i', audio_file,
            '-vf', "hflip,scale=iw*1.04:ih*1.04,crop=iw:ih,setpts=0.95*PTS",
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-shortest',
            output_file
        ]
        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.communicate()
        
        await update.message.reply_text("✅ ပြီးပါပြီ! TikTok ဗီဒီယိုကို ပို့ပေးလိုက်ပါပြီ။")
        with open(output_file, 'rb') as f:
            await update.message.reply_video(video=f)
            
    except Exception as e:
        await update.message.reply_text(f"❌ အမှားအယွင်း ဖြစ်ပွားခဲ့သည်: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot is running...")
    app.run_polling()
    
