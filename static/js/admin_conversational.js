(() => {
  const userIdInput = document.getElementById('user-id');
  const sessionIdInput = document.getElementById('session-id');
  const messageInput = document.getElementById('message');
  const connectButton = document.getElementById('connect-btn');
  const sendButton = document.getElementById('send-btn');
  const connectionStatus = document.getElementById('connection-status');
  const turnStatus = document.getElementById('turn-status');
  const chatLog = document.getElementById('chat-log');

  let socket = null;
  let isConnected = false;
  let currentSessionId = '';
  let activeTurnId = null;

  const assistantDrafts = new Map();
  let audioContext = null;
  let nextPlayAt = 0;

  function setConnectionStatus(text, className) {
    connectionStatus.textContent = text;
    connectionStatus.className = `inline-flex items-center px-2 py-1 rounded ${className}`;
  }

  function setTurnStatus(text) {
    turnStatus.textContent = text || '';
  }

  function scrollToBottom() {
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function appendMessage(role, text) {
    const wrapper = document.createElement('div');
    wrapper.className = role === 'user' ? 'text-right' : 'text-left';

    const bubble = document.createElement('div');
    bubble.className = role === 'user'
      ? 'inline-block max-w-[85%] rounded-lg px-3 py-2 bg-blue-600 text-white text-sm whitespace-pre-wrap'
      : 'inline-block max-w-[85%] rounded-lg px-3 py-2 bg-white border border-gray-200 text-gray-900 text-sm whitespace-pre-wrap';
    bubble.textContent = text;

    wrapper.appendChild(bubble);
    chatLog.appendChild(wrapper);
    scrollToBottom();
    return bubble;
  }

  function appendSystemMessage(text, isError = false) {
    const row = document.createElement('div');
    row.className = `text-xs ${isError ? 'text-red-600' : 'text-gray-500'}`;
    row.textContent = text;
    chatLog.appendChild(row);
    scrollToBottom();
  }

  function appendSourcesMessage(knowledgeHits, webHits) {
    const wrapper = document.createElement('div');
    wrapper.className = 'text-xs text-gray-600 bg-white border border-gray-200 rounded p-2 space-y-1';

    const knowledgeCount = Array.isArray(knowledgeHits) ? knowledgeHits.length : 0;
    const webCount = Array.isArray(webHits) ? webHits.length : 0;
    const header = document.createElement('div');
    header.className = 'font-medium text-gray-700';
    header.textContent = `Sources: knowledge=${knowledgeCount}, web=${webCount}`;
    wrapper.appendChild(header);

    const list = document.createElement('ul');
    list.className = 'list-disc ml-4 space-y-0.5';

    const addLinkRow = (prefix, item) => {
      const li = document.createElement('li');
      const title = String(item.title || 'Untitled');
      const url = String(item.url || '').trim();
      if (url) {
        const link = document.createElement('a');
        link.href = url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.className = 'text-blue-600 hover:underline';
        link.textContent = `${prefix} ${title}`;
        li.appendChild(link);
      } else {
        li.textContent = `${prefix} ${title}`;
      }
      list.appendChild(li);
    };

    if (knowledgeCount === 0 && webCount === 0) {
      const li = document.createElement('li');
      li.textContent = 'No source hits.';
      list.appendChild(li);
    } else {
      (knowledgeHits || []).forEach((hit, idx) => addLinkRow(`[K${idx + 1}]`, hit));
      (webHits || []).forEach((hit, idx) => addLinkRow(`[W${idx + 1}]`, hit));
    }

    wrapper.appendChild(list);
    chatLog.appendChild(wrapper);
    scrollToBottom();
  }

  function getAssistantBubble(turnId) {
    if (assistantDrafts.has(turnId)) {
      return assistantDrafts.get(turnId);
    }
    const bubble = appendMessage('assistant', '');
    assistantDrafts.set(turnId, bubble);
    return bubble;
  }

  function base64ToBytes(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  }

  async function ensureAudioContext() {
    if (!window.AudioContext && !window.webkitAudioContext) {
      return null;
    }
    if (!audioContext) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      audioContext = new AudioContextClass({ sampleRate: 16000 });
      nextPlayAt = 0;
    }
    if (audioContext.state === 'suspended') {
      await audioContext.resume();
    }
    return audioContext;
  }

  async function playPcmChunk(chunkB64) {
    const ctx = await ensureAudioContext();
    if (!ctx) {
      return;
    }

    const bytes = base64ToBytes(chunkB64);
    const sampleCount = Math.floor(bytes.length / 2);
    if (sampleCount <= 0) {
      return;
    }

    const buffer = ctx.createBuffer(1, sampleCount, 16000);
    const channelData = buffer.getChannelData(0);
    for (let i = 0; i < sampleCount; i += 1) {
      let sample = bytes[i * 2] | (bytes[i * 2 + 1] << 8);
      if (sample >= 0x8000) {
        sample -= 0x10000;
      }
      channelData[i] = sample / 32768;
    }

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);

    if (nextPlayAt < ctx.currentTime) {
      nextPlayAt = ctx.currentTime + 0.01;
    }
    source.start(nextPlayAt);
    nextPlayAt += buffer.duration;
  }

  function closeSocket() {
    if (socket) {
      socket.close();
    }
    socket = null;
    isConnected = false;
    setConnectionStatus('Disconnected', 'bg-gray-100 text-gray-600');
  }

  function buildWsUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/admin/conversational/ws`;
  }

  function sendEvent(payload) {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      appendSystemMessage('WebSocket is not connected.', true);
      return false;
    }
    socket.send(JSON.stringify(payload));
    return true;
  }

  function handleSocketEvent(payload) {
    const type = payload.type;
    if (type === 'ready') {
      currentSessionId = payload.session_id || '';
      sessionIdInput.value = currentSessionId;
      appendSystemMessage(`Session ready: ${currentSessionId}`);
      return;
    }

    if (type === 'turn_started') {
      activeTurnId = payload.turn_id;
      setTurnStatus(`Turn ${activeTurnId} in progress...`);
      return;
    }

    if (type === 'assistant_delta') {
      const bubble = getAssistantBubble(payload.turn_id || activeTurnId || 'turn');
      bubble.textContent += payload.text_delta || '';
      scrollToBottom();
      return;
    }

    if (type === 'assistant_final') {
      const turnId = payload.turn_id || activeTurnId || 'turn';
      const bubble = getAssistantBubble(turnId);
      bubble.textContent = payload.text || bubble.textContent;
      scrollToBottom();
      return;
    }

    if (type === 'sources') {
      appendSourcesMessage(payload.knowledge_hits || [], payload.web_hits || []);
      return;
    }

    if (type === 'audio_chunk') {
      void playPcmChunk(payload.chunk_b64 || '');
      return;
    }

    if (type === 'audio_end') {
      return;
    }

    if (type === 'turn_complete') {
      activeTurnId = null;
      setTurnStatus('');
      return;
    }

    if (type === 'error') {
      const message = payload.message || 'Unknown error';
      appendSystemMessage(`Error: ${message}`, true);
      setTurnStatus('');
      activeTurnId = null;
      return;
    }

    if (type === 'pong') {
      return;
    }

    appendSystemMessage(`Unhandled event: ${type}`);
  }

  async function connect() {
    closeSocket();

    const userId = Number(userIdInput.value);
    if (!Number.isInteger(userId) || userId <= 0) {
      appendSystemMessage('Enter a valid positive user ID before connecting.', true);
      return;
    }

    try {
      const healthResponse = await fetch('/admin/conversational/health');
      if (!healthResponse.ok) {
        appendSystemMessage('Failed to check conversational health.', true);
        return;
      }
      const health = await healthResponse.json();
      if (!health.ready) {
        const reasons = (health.readiness_reasons || []).join(', ') || 'unknown';
        appendSystemMessage(`Conversational backend is not ready: ${reasons}`, true);
        return;
      }
    } catch (error) {
      appendSystemMessage(`Health check failed: ${error}`, true);
      return;
    }

    await ensureAudioContext();

    socket = new WebSocket(buildWsUrl());
    setConnectionStatus('Connecting...', 'bg-yellow-100 text-yellow-700');

    socket.addEventListener('open', () => {
      isConnected = true;
      setConnectionStatus('Connected', 'bg-green-100 text-green-700');
      sendEvent({
        type: 'init',
        user_id: userId,
        session_id: sessionIdInput.value.trim() || null,
      });
    });

    socket.addEventListener('message', (event) => {
      try {
        const payload = JSON.parse(event.data);
        handleSocketEvent(payload);
      } catch (error) {
        appendSystemMessage(`Invalid event payload: ${error}`, true);
      }
    });

    socket.addEventListener('close', () => {
      isConnected = false;
      setConnectionStatus('Disconnected', 'bg-gray-100 text-gray-600');
      setTurnStatus('');
    });

    socket.addEventListener('error', () => {
      appendSystemMessage('WebSocket connection error.', true);
    });
  }

  async function sendMessage() {
    if (!isConnected) {
      appendSystemMessage('Connect first.', true);
      return;
    }

    const text = messageInput.value.trim();
    if (!text) {
      return;
    }

    await ensureAudioContext();

    const turnId = `turn_${Date.now()}`;
    appendMessage('user', text);
    messageInput.value = '';

    sendEvent({
      type: 'user_message',
      turn_id: turnId,
      text,
    });
  }

  connectButton.addEventListener('click', () => {
    void connect();
  });

  sendButton.addEventListener('click', () => {
    void sendMessage();
  });

  messageInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      void sendMessage();
    }
  });
})();
