# Copyright 2026 Google LLC
# Real-time Voice Conversational Interface for GastroConcierge
# Built with Gemini Live API (gemini-live-api-dev)

import asyncio
import base64
import json
import logging
import os
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_concierge")

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-f85cd1da7915")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
LIVE_MODEL = "gemini-live-2.5-flash-native-audio"

app = FastAPI(title="GastroConcierge Live Voice API")

HTML_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GastroConcierge — Habla en Vivo (Gemini Live API)</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0f141c;
            --surface: #1a2230;
            --surface-hover: #232d3f;
            --primary: #f59e0b;
            --primary-glow: rgba(245, 158, 11, 0.35);
            --secondary: #10b981;
            --text: #f3f4f6;
            --text-dim: #9ca3af;
            --border: #2e3a4e;
            --danger: #ef4444;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Outfit', -apple-system, sans-serif;
            background: radial-gradient(circle at top, #1e293b 0%, var(--bg) 70%);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 24px 16px;
        }

        .header {
            text-align: center;
            max-width: 680px;
            margin-bottom: 24px;
        }

        .header h1 {
            font-size: 2.2rem;
            font-weight: 700;
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
        }

        .header h1 span {
            color: var(--primary);
            text-shadow: 0 0 20px var(--primary-glow);
        }

        .header p {
            color: var(--text-dim);
            margin-top: 8px;
            font-size: 1rem;
        }

        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 20px;
            width: 100%;
            max-width: 720px;
            padding: 28px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.5);
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        .voice-controls {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
            flex-wrap: wrap;
            gap: 12px;
        }

        .voice-select-wrap {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.95rem;
            color: var(--text-dim);
        }

        select {
            background: var(--bg);
            border: 1px solid var(--border);
            color: #fff;
            padding: 8px 14px;
            border-radius: 10px;
            outline: none;
            font-family: inherit;
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
        }

        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--text-dim);
        }

        .status-dot.active {
            background: var(--secondary);
            box-shadow: 0 0 10px var(--secondary);
            animation: pulse 1.5s infinite;
        }

        .status-dot.speaking {
            background: var(--primary);
            box-shadow: 0 0 12px var(--primary);
            animation: pulse 0.8s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.8; }
            50% { transform: scale(1.2); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.8; }
        }

        .center-action {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 16px;
            padding: 24px 0;
        }

        .mic-btn {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            border: none;
            cursor: pointer;
            background: linear-gradient(135deg, #f59e0b, #d97706);
            color: white;
            font-size: 2.2rem;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 10px 25px var(--primary-glow);
            transition: all 0.2s ease;
        }

        .mic-btn:hover {
            transform: scale(1.06);
        }

        .mic-btn.active {
            background: linear-gradient(135deg, #ef4444, #dc2626);
            box-shadow: 0 0 35px rgba(239, 68, 68, 0.6);
            animation: ripple 2s infinite;
        }

        @keyframes ripple {
            0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.6); }
            70% { box-shadow: 0 0 0 25px rgba(239, 68, 68, 0); }
            100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }

        .call-instruction {
            font-size: 0.95rem;
            color: var(--text-dim);
            text-align: center;
        }

        .transcript-box {
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 14px;
            height: 220px;
            overflow-y: auto;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            font-size: 0.92rem;
        }

        .bubble {
            padding: 10px 14px;
            border-radius: 12px;
            max-width: 85%;
            line-height: 1.4;
        }

        .bubble.agent {
            background: rgba(245, 158, 11, 0.15);
            border: 1px solid rgba(245, 158, 11, 0.3);
            align-self: flex-start;
            color: #fde68a;
        }

        .bubble.user {
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.3);
            align-self: flex-end;
            color: #a7f3d0;
        }

        .text-input-row {
            display: flex;
            gap: 10px;
        }

        .text-input-row input {
            flex: 1;
            background: var(--bg);
            border: 1px solid var(--border);
            padding: 12px 16px;
            border-radius: 12px;
            color: #fff;
            outline: none;
            font-family: inherit;
        }

        .text-input-row button {
            background: var(--surface-hover);
            border: 1px solid var(--border);
            color: #fff;
            padding: 0 20px;
            border-radius: 12px;
            cursor: pointer;
            font-weight: 600;
        }

        .tips {
            font-size: 0.85rem;
            color: var(--text-dim);
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎙️ Gastro<span>Concierge</span> Live</h1>
        <p>Conversación bidireccional en tiempo real con Gemini Live API y baja latencia.</p>
    </div>

    <div class="card">
        <div class="voice-controls">
            <div class="voice-select-wrap">
                <label for="voiceSelect">Voz del Concierge:</label>
                <select id="voiceSelect">
                    <option value="Aoede" selected>Aoede (Cálida y elegante)</option>
                    <option value="Kore">Kore (Amable y suave)</option>
                    <option value="Puck">Puck (Enérgica)</option>
                    <option value="Fenrir">Fenrir (Grave y formal)</option>
                    <option value="Charon">Charon (Profunda)</option>
                </select>
            </div>
            <div class="status-badge">
                <div class="status-dot" id="statusDot"></div>
                <span id="statusText">Desconectado</span>
            </div>
        </div>

        <div class="center-action">
            <button class="mic-btn" id="micBtn" onclick="toggleConversation()">🎙️</button>
            <div class="call-instruction" id="instructionText">
                Haz clic en el micrófono para hablar directamente con GastroConcierge
            </div>
        </div>

        <div class="transcript-box" id="transcriptBox">
            <div class="bubble agent">
                🤖 <strong>GastroConcierge:</strong> ¡Bienvenido! Presiona el micrófono y cuéntame qué se te antoja ordenar hoy o pregúntame por maridajes y recomendaciones del menú.
            </div>
        </div>

        <div class="text-input-row">
            <input type="text" id="textPrompt" placeholder="O escribe tu mensaje aquí..." onkeypress="handleKey(event)">
            <button onclick="sendTextMessage()">Enviar</button>
        </div>

        <div class="tips">
            💡 <strong>Barge-in habilitado:</strong> Puedes hablar en cualquier momento para interrumpir al concierge. Usa auriculares para evitar eco.
        </div>
    </div>

    <script>
        let ws = null;
        let isConnected = false;
        let audioContext = null;
        let micStream = null;
        let scriptProcessor = null;
        let playbackContext = null;
        let nextAudioTime = 0;
        let activeSources = [];

        const micBtn = document.getElementById('micBtn');
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        const instructionText = document.getElementById('instructionText');
        const transcriptBox = document.getElementById('transcriptBox');
        const textPrompt = document.getElementById('textPrompt');
        const voiceSelect = document.getElementById('voiceSelect');

        function appendMessage(sender, text) {
            const div = document.createElement('div');
            div.className = `bubble ${sender}`;
            div.innerHTML = `${sender === 'user' ? '🗣️' : '🤖'} <strong>${sender === 'user' ? 'Tú' : 'GastroConcierge'}:</strong> ${text}`;
            transcriptBox.appendChild(div);
            transcriptBox.scrollTop = transcriptBox.scrollHeight;
        }

        async function initAudio() {
            if (!playbackContext) {
                playbackContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
            }
            if (playbackContext.state === 'suspended') {
                await playbackContext.resume();
            }
        }

        function playPcmChunk(base64Data) {
            try {
                const binaryString = atob(base64Data);
                const bytes = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                }
                const int16Array = new Int16Array(bytes.buffer);
                const float32Array = new Float32Array(int16Array.length);
                for (let i = 0; i < int16Array.length; i++) {
                    float32Array[i] = int16Array[i] / 32768.0;
                }

                const audioBuffer = playbackContext.createBuffer(1, float32Array.length, 24000);
                audioBuffer.getChannelData(0).set(float32Array);

                const source = playbackContext.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(playbackContext.destination);

                const now = playbackContext.currentTime;
                if (nextAudioTime < now) {
                    nextAudioTime = now;
                }

                source.start(nextAudioTime);
                nextAudioTime += audioBuffer.duration;
                activeSources.push(source);

                statusDot.className = 'status-dot speaking';
                statusText.innerText = 'Hablando...';

                source.onended = () => {
                    const idx = activeSources.indexOf(source);
                    if (idx > -1) activeSources.splice(idx, 1);
                    if (activeSources.length === 0 && isConnected) {
                        statusDot.className = 'status-dot active';
                        statusText.innerText = 'Escuchando...';
                    }
                };
            } catch (err) {
                console.error('Error playing audio chunk:', err);
            }
        }

        function clearAudioPlayback() {
            for (const src of activeSources) {
                try { src.stop(); } catch(e) {}
            }
            activeSources = [];
            if (playbackContext) {
                nextAudioTime = playbackContext.currentTime;
            }
        }

        async function startMicStream() {
            audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    sampleRate: 16000,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });

            const source = audioContext.createMediaStreamSource(micStream);
            scriptProcessor = audioContext.createScriptProcessor(2048, 1, 1);

            scriptProcessor.onaudioprocess = (e) => {
                if (!isConnected || !ws || ws.readyState !== WebSocket.OPEN) return;
                const inputData = e.inputBuffer.getChannelData(0);
                const pcm16 = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    const s = Math.max(-1, Math.min(1, inputData[i]));
                    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }

                let binary = '';
                const bytes = new Uint8Array(pcm16.buffer);
                for (let i = 0; i < bytes.byteLength; i++) {
                    binary += String.fromCharCode(bytes[i]);
                }
                const base64Audio = btoa(binary);

                ws.send(JSON.stringify({
                    type: 'audio',
                    data: base64Audio
                }));
            };

            source.connect(scriptProcessor);
            scriptProcessor.connect(audioContext.destination);
        }

        function stopMicStream() {
            if (scriptProcessor) {
                scriptProcessor.disconnect();
                scriptProcessor = null;
            }
            if (micStream) {
                micStream.getTracks().forEach(track => track.stop());
                micStream = null;
            }
            if (audioContext) {
                audioContext.close();
                audioContext = null;
            }
        }

        async function toggleConversation() {
            if (isConnected) {
                disconnectLive();
            } else {
                await connectLive();
            }
        }

        async function connectLive() {
            await initAudio();
            const voice = voiceSelect.value;
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${wsProtocol}//${window.location.host}/ws/live?voice=${voice}`;

            statusDot.className = 'status-dot';
            statusText.innerText = 'Conectando con Gemini Live...';

            ws = new WebSocket(wsUrl);

            ws.onopen = async () => {
                isConnected = true;
                micBtn.className = 'mic-btn active';
                micBtn.innerText = '⏹️';
                statusDot.className = 'status-dot active';
                statusText.innerText = 'Conectado (En vivo)';
                instructionText.innerText = 'Habla con el micrófono o escribe abajo. Di "Detener" o pulsa el botón para terminar.';
                try {
                    await startMicStream();
                } catch (e) {
                    console.warn('Microphone permission not granted or available:', e);
                    instructionText.innerText = 'Micrófono no disponible en este entorno, puedes chatear usando texto abajo con respuestas de voz.';
                }
            };

            let currentAgentResponse = "";

            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'audio') {
                    playPcmChunk(msg.data);
                } else if (msg.type === 'interrupted') {
                    clearAudioPlayback();
                } else if (msg.type === 'text') {
                    currentAgentResponse += msg.text;
                } else if (msg.type === 'turn_complete') {
                    if (currentAgentResponse.trim()) {
                        appendMessage('agent', currentAgentResponse);
                        currentAgentResponse = "";
                    }
                }
            };

            ws.onclose = () => {
                disconnectLive();
            };

            ws.onerror = (err) => {
                console.error('WebSocket error:', err);
                disconnectLive();
            };
        }

        function disconnectLive() {
            isConnected = false;
            stopMicStream();
            clearAudioPlayback();
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.close();
            }
            ws = null;
            micBtn.className = 'mic-btn';
            micBtn.innerText = '🎙️';
            statusDot.className = 'status-dot';
            statusText.innerText = 'Desconectado';
            instructionText.innerText = 'Haz clic en el micrófono para hablar directamente con GastroConcierge';
        }

        function sendTextMessage() {
            const text = textPrompt.value.trim();
            if (!text) return;
            appendMessage('user', text);
            textPrompt.value = '';

            if (isConnected && ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'text', text: text }));
            } else {
                connectLive().then(() => {
                    setTimeout(() => {
                        if (ws && ws.readyState === WebSocket.OPEN) {
                            ws.send(JSON.stringify({ type: 'text', text: text }));
                        }
                    }, 500);
                });
            }
        }

        function handleKey(e) {
            if (e.key === 'Enter') {
                sendTextMessage();
            }
        }
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def get_index():
    return HTMLResponse(content=HTML_PAGE)


@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket, voice: str = "Aoede"):
    await websocket.accept()
    logger.info(f"New client connected with voice: {voice}")

    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

    live_config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            )
        ),
        system_instruction=types.Content(
            parts=[
                types.Part(
                    text="""Eres GastroConcierge, un concierge y asesor culinario inteligente, sofisticado, cálido y acogedor en un restaurante gourmet.
Hablas en español de forma natural, fluida, concisa y profesional como un maître o sommelier atendiendo en la mesa.
Ayudas al cliente con:
1. Recomendaciones del menú (Tacos al Pastor Gourmet, Hamachi Crudo, Gnocchi con Trufa Negra, Volcán de Matcha).
2. Maridajes ideales de cócteles o vinos (Margaritas de autor, Spritz, etc.).
3. Armar pedidos y resolver dudas sobre ingredientes, alergias y tiempos de cocina.
Mantén tus respuestas habladas amables, apetitosas y breves para una conversación fluida sin monólogos largos."""
                )
            ]
        ),
    )

    try:
        async with client.aio.live.connect(model=LIVE_MODEL, config=live_config) as session:
            logger.info("Connected to Gemini Live session.")

            async def receive_from_gemini():
                try:
                    async for response in session.receive():
                        server_content = response.server_content
                        if not server_content:
                            continue

                        if server_content.interrupted:
                            logger.info("Interruption detected (Barge-in)")
                            await websocket.send_json({"type": "interrupted"})

                        if server_content.model_turn:
                            for part in server_content.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    audio_b64 = base64.b64encode(part.inline_data.data).decode("utf-8")
                                    await websocket.send_json({
                                        "type": "audio",
                                        "data": audio_b64,
                                    })
                                if part.text:
                                    await websocket.send_json({
                                        "type": "text",
                                        "text": part.text,
                                    })

                        if server_content.turn_complete:
                            await websocket.send_json({"type": "turn_complete"})
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error receiving from Gemini: {e}")

            gemini_task = asyncio.create_task(receive_from_gemini())

            try:
                while True:
                    data = await websocket.receive_text()
                    msg = json.loads(data)
                    msg_type = msg.get("type")

                    if msg_type == "audio":
                        pcm_bytes = base64.b64decode(msg.get("data", ""))
                        if pcm_bytes:
                            await session.send_realtime_input(
                                audio=types.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000")
                            )
                    elif msg_type == "text":
                        text = msg.get("text", "")
                        if text:
                            await session.send_realtime_input(text=text)
                    elif msg_type == "audio_stream_end":
                        await session.send_realtime_input(audio_stream_end=True)
            except WebSocketDisconnect:
                logger.info("Client disconnected.")
            finally:
                gemini_task.cancel()
    except Exception as e:
        logger.error(f"Live API error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8088)
