import cv2
import subprocess
import os

def apply_attack(input_path, output_path):
    # FFmpeg pipeline: 9:16 Crop + Speed up + Meme Overlay + High Compression
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', (
            "crop=ih*(9/16):ih, " # TikTok Style
            "setpts=0.9*PTS, "    # 1.1x Speed
            "drawtext=text='LIVE STREAM 2026':fontcolor=yellow:fontsize=45:x=(w-text_w)/2:y=150"
        ),
        '-c:v', 'libx264', '-crf', '32', '-preset', 'ultrafast',
        output_path
    ]
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    # Test on one of your clean clips
    apply_attack('clean_broadcast.mp4', 'ml_context/adversarial_tests/attack_v1.mp4')