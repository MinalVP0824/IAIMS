"""
visualize_3d.py - Advanced 3D Memory Graph with Smart Connections
Fixed: Nodes now visible with proper sizing and positioning
"""

import argparse
import json
import threading
import time
import webbrowser
from datetime import datetime
from collections import defaultdict
import os
import networkx as nx
import numpy as np
import requests
from flask import Flask, render_template_string
from flask_sock import Sock

# Membrain config
MEMBRAIN_API_KEY = os.getenv("MEMBRAIN_API_KEY")
MEMBRAIN_BASE_URL = "https://mem-brain-api-cutover-v4-production.up.railway.app/api/v1"
MEMBRAIN_HEADERS  = {
    "X-API-Key":    MEMBRAIN_API_KEY,
    "Content-Type": "application/json",
}

FETCH_QUERIES = [
    "clawmind ishan hackathon project memory",
    "whatsapp facebook message call reminder",
    "user query ai response action result",
    "meeting schedule deadline task",
    "personal contact business relationship",
]

DEFAULT_PORT     = 5050
DEFAULT_INTERVAL = 4

# Enhanced color palette for galaxy theme
COLOR_MAP = {
    "whatsapp":   "#25D366",
    "message":    "#4CAF50",
    "call":       "#FF9800",
    "user":       "#2196F3",
    "query":      "#00BCD4",
    "ai":         "#9C27B0",
    "response":   "#FF69B4",
    "permission": "#FFC107",
    "action":     "#FF5722",
    "success":    "#8BC34A",
    "memory":     "#3F51B5",
    "result":     "#009688",
    "reminder":   "#FF4081",
    "meeting":    "#E91E63",
    "schedule":   "#FF6B6B",
    "deadline":   "#F44336",
    "task":       "#FF9800",
    "business":   "#795548",
    "personal":   "#9C27B0",
    "default":    "#9E9E9E",
}


def fetch_all_memories():
    """Fetch memories with enhanced metadata extraction"""
    seen, combined = set(), []
    for query in FETCH_QUERIES:
        try:
            res = requests.post(
                f"{MEMBRAIN_BASE_URL}/memories/search",
                headers=MEMBRAIN_HEADERS,
                json={"query": query, "k": 50},
                timeout=10,
            )
            if res.status_code != 200:
                continue
            data = res.json()
            items = data if isinstance(data, list) else (
                data.get("results") or data.get("memories") or
                data.get("data") or data.get("items") or []
            )
            for item in items:
                if isinstance(item, dict):
                    content = item.get("content") or item.get("text") or item.get("memory") or ""
                    tags = item.get("tags", [])
                    ts = item.get("timestamp") or item.get("created_at") or ""
                    metadata = item.get("metadata", {})
                elif isinstance(item, str):
                    content, tags, ts, metadata = item, [], "", {}
                else:
                    continue
                
                content = content.strip()
                if content and content not in seen:
                    seen.add(content)
                    if not tags:
                        lower = content.lower()
                        tags = [k for k in COLOR_MAP if k != "default" and k in lower]
                    
                    # Extract urgency
                    urgency = "normal"
                    if any(word in content.lower() for word in ["urgent", "asap", "important", "critical"]):
                        urgency = "high"
                    elif any(word in content.lower() for word in ["reminder", "deadline", "due"]):
                        urgency = "medium"
                    
                    combined.append({
                        "content": content,
                        "tags": tags[:3] if len(tags) > 3 else tags,  # Limit tags
                        "timestamp": ts,
                        "urgency": urgency,
                        "type": tags[0] if tags else "general",
                        "metadata": metadata
                    })
        except Exception as e:
            print(f"[poll] error ({query[:20]}...): {e}")
    return combined


def calculate_relevance(mem1, mem2):
    """Calculate relevance score between two memories"""
    score = 0
    
    # Shared tags (weight: 3)
    shared_tags = set(mem1.get("tags", [])) & set(mem2.get("tags", []))
    score += len(shared_tags) * 3
    
    # Shared urgency level (weight: 2)
    if mem1.get("urgency") == mem2.get("urgency"):
        score += 2
    
    # Same type (weight: 2)
    if mem1.get("type") == mem2.get("type"):
        score += 2
    
    # Keyword matching (weight: 1 per match)
    words1 = set(mem1["content"].lower().split())
    words2 = set(mem2["content"].lower().split())
    common_words = words1 & words2
    score += min(len(common_words), 5)
    
    return score


def build_graph_data(memories, relevance_threshold=3):
    """Build graph with smart relevance-based connections"""
    if not memories:
        return {"nodes": [], "edges": [], "stats": {"memories": 0, "connections": 0, "avg_relevance": 0}, "updated_at": "-"}
    
    G = nx.Graph()
    
    # Add nodes with larger sizes
    for i, mem in enumerate(memories):
        tags = mem.get("tags", [])
        color = next((COLOR_MAP[t] for t in tags if t in COLOR_MAP), COLOR_MAP["default"])
        
        # Larger node sizes for better visibility
        size = 18  # Base size increased
        if mem.get("urgency") == "high":
            size = 28
        elif mem.get("urgency") == "medium":
            size = 23
        size += len(tags) * 2
        
        G.add_node(i, 
                   label=mem["content"][:50],
                   full=mem["content"],
                   tags=", ".join(tags[:3]) or "-",
                   color=color,
                   timestamp=mem.get("timestamp", ""),
                   urgency=mem.get("urgency", "normal"),
                   mem_type=mem.get("type", "general"),
                   size=size)
    
    # Add edges based on relevance
    for i in range(len(memories)):
        for j in range(i + 1, len(memories)):
            relevance = calculate_relevance(memories[i], memories[j])
            if relevance >= relevance_threshold:
                G.add_edge(i, j, weight=relevance, relevance=relevance)
    
    # Better 3D layout with more spread
    pos = nx.spring_layout(G, dim=3, seed=42, k=5, iterations=150)
    
    # Scale positions to be more spread out
    nodes = []
    for n, d in G.nodes(data=True):
        nodes.append({
            "id": n,
            "x": float(pos[n][0] * 3.5),  # Scale up positions
            "y": float(pos[n][1] * 3.5),
            "z": float(pos[n][2] * 3.5),
            "label": d["label"],
            "full": d["full"],
            "tags": d["tags"],
            "color": d["color"],
            "timestamp": d["timestamp"],
            "urgency": d["urgency"],
            "type": d["mem_type"],
            "degree": G.degree(n),
            "size": d["size"]
        })
    
    edges = [{
        "x": [float(pos[u][0] * 3.5), float(pos[v][0] * 3.5)],
        "y": [float(pos[u][1] * 3.5), float(pos[v][1] * 3.5)],
        "z": [float(pos[u][2] * 3.5), float(pos[v][2] * 3.5)],
        "relevance": G[u][v].get("relevance", 3)
    } for u, v in G.edges()]
    
    avg_relevance = sum(e["relevance"] for e in edges) / len(edges) if edges else 0
    
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "memories": len(memories),
            "connections": G.number_of_edges(),
            "avg_relevance": round(avg_relevance, 1)
        },
        "updated_at": datetime.now().strftime("%H:%M:%S")
    }


class State:
    def __init__(self, interval):
        self.interval, self.lock = interval, threading.Lock()
        self.graph_data, self.clients = {}, []
        self._last_count = -1

    def poll_loop(self):
        while True:
            try:
                mems = fetch_all_memories()
                if len(mems) != self._last_count:
                    self._last_count = len(mems)
                    data = build_graph_data(mems)
                    with self.lock:
                        self.graph_data = data
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {len(mems)} memories — {data['stats']['connections']} connections")
                    self.broadcast()
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No change ({len(mems)} memories)")
            except Exception as e:
                print(f"[poll] loop error: {e}")
            time.sleep(self.interval)

    def broadcast(self):
        with self.lock:
            payload = json.dumps(self.graph_data)
        dead = []
        for ws in list(self.clients):
            try:
                ws.send(payload)
            except:
                dead.append(ws)
        for ws in dead:
            try:
                self.clients.remove(ws)
            except:
                pass


PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Membrain Galaxy Graph</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', 'Poppins', 'Arial', sans-serif;
    overflow: hidden;
    transition: all 0.3s ease;
}

body.dark {
    background: #0a0a2a;
    color: #ffffff;
}

body.light {
    background: #f0f0ff;
    color: #1a1a2e;
}

#graph {
    width: 100vw;
    height: 100vh;
    position: relative;
}

/* Control Panel */
.control-panel {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 100;
    display: flex;
    gap: 12px;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(10px);
    padding: 12px 20px;
    border-radius: 40px;
    border: 1px solid rgba(138, 43, 226, 0.5);
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
}

.theme-toggle, .reset-btn {
    background: linear-gradient(135deg, #8a2be2, #4a0e4e);
    border: none;
    color: white;
    padding: 8px 16px;
    border-radius: 30px;
    cursor: pointer;
    font-size: 14px;
    font-weight: bold;
    transition: transform 0.2s, box-shadow 0.2s;
}

.theme-toggle:hover, .reset-btn:hover {
    transform: scale(1.05);
    box-shadow: 0 0 15px rgba(138, 43, 226, 0.5);
}

/* Stats Panel */
.stats-panel {
    position: fixed;
    bottom: 20px;
    left: 20px;
    z-index: 100;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(10px);
    padding: 12px 20px;
    border-radius: 20px;
    border: 1px solid rgba(138, 43, 226, 0.5);
    font-size: 12px;
    font-family: monospace;
}

.stats-panel div {
    margin: 4px 0;
}

.stats-panel .highlight {
    color: #8a2be2;
    font-weight: bold;
}

/* Toast Notification */
.toast {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: linear-gradient(135deg, #8a2be2, #4a0e4e);
    color: white;
    padding: 12px 24px;
    border-radius: 30px;
    font-size: 13px;
    opacity: 0;
    transition: opacity 0.4s;
    z-index: 200;
    pointer-events: none;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
}

.toast.show {
    opacity: 1;
}

/* Legend */
.legend {
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 100;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(8px);
    padding: 12px;
    border-radius: 12px;
    font-size: 10px;
    border: 1px solid rgba(138, 43, 226, 0.3);
    max-width: 180px;
}

.legend h4 {
    margin-bottom: 8px;
    font-size: 11px;
    color: #8a2be2;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 4px 0;
}

.legend-color {
    width: 12px;
    height: 12px;
    border-radius: 50%;
}

.loading {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    text-align: center;
    z-index: 1000;
    background: rgba(0, 0, 0, 0.8);
    padding: 20px 40px;
    border-radius: 20px;
    backdrop-filter: blur(10px);
}

.spinner {
    width: 40px;
    height: 40px;
    border: 3px solid rgba(138, 43, 226, 0.3);
    border-top-color: #8a2be2;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 12px;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.hidden {
    display: none;
}
</style>
</head>
<body class="dark">
<div class="control-panel">
    <button class="theme-toggle" onclick="toggleTheme()">🌓 Theme</button>
    <button class="reset-btn" onclick="resetCamera()">🎯 Reset Camera</button>
</div>
<div class="stats-panel" id="statsPanel">
    <div>📊 <span class="highlight">MEMBRAIN GALAXY</span></div>
    <div>💾 Memories: <span id="memCount">-</span></div>
    <div>🔗 Connections: <span id="connCount">-</span></div>
    <div>⭐ Avg Relevance: <span id="avgRelevance">-</span></div>
    <div>🕐 Updated: <span id="updateTime">-</span></div>
</div>
<div class="legend">
    <h4>📌 Node Types</h4>
    <div class="legend-item"><div class="legend-color" style="background: #25D366;"></div><span>WhatsApp</span></div>
    <div class="legend-item"><div class="legend-color" style="background: #FF9800;"></div><span>Call/Urgent</span></div>
    <div class="legend-item"><div class="legend-color" style="background: #2196F3;"></div><span>User Query</span></div>
    <div class="legend-item"><div class="legend-color" style="background: #9C27B0;"></div><span>AI Response</span></div>
    <div class="legend-item"><div class="legend-color" style="background: #F44336;"></div><span>Deadline</span></div>
</div>
<div class="toast" id="toast"></div>
<div class="loading hidden" id="loading">
    <div class="spinner"></div>
    <div>Loading galaxy...</div>
</div>
<div id="graph"></div>

<script>
let currentTheme = 'dark';
let currentGraph = null;

function showToast(msg, isError = false) {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.style.background = isError ? 'linear-gradient(135deg, #f44336, #c62828)' : 'linear-gradient(135deg, #8a2be2, #4a0e4e)';
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

function toggleTheme() {
    currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.body.className = currentTheme;
    
    const bgColor = currentTheme === 'dark' ? 'black' : '#f0f0ff';
    const textColor = currentTheme === 'dark' ? 'white' : '#1a1a2e';
    
    Plotly.relayout('graph', {
        'paper_bgcolor': bgColor,
        'plot_bgcolor': bgColor,
        'scene.bgcolor': bgColor,
        'font.color': textColor
    });
    
    showToast(`🌓 ${currentTheme === 'dark' ? 'Dark' : 'Light'} mode activated`);
}

function resetCamera() {
    Plotly.relayout('graph', {
        'scene.camera': {
            eye: {x: 12, y: 8, z: 10},
            up: {x: 0, y: 0, z: 1},
            center: {x: 0, y: 0, z: 0}
        }
    });
    showToast('🎯 Camera reset');
}

function generateStars(count, theme) {
    const colors = theme === 'dark' ? 
        ['#FFFFFF', '#FFE4B5', '#B0C4DE', '#FFB6C1'] :
        ['#4a4a6a', '#5a5a7a', '#6a6a8a', '#7a7a9a'];
    
    return {
        x: Array.from({length: count}, () => (Math.random() - 0.5) * 35),
        y: Array.from({length: count}, () => (Math.random() - 0.5) * 28),
        z: Array.from({length: count}, () => (Math.random() - 0.5) * 35),
        mode: 'markers',
        type: 'scatter3d',
        marker: {
            size: Array.from({length: count}, () => Math.random() * 2.5 + 0.8),
            color: colors[Math.floor(Math.random() * colors.length)],
            opacity: 0.7,
            symbol: 'circle'
        },
        hoverinfo: 'none',
        showlegend: false
    };
}

function updateGraph(data) {
    if (!data.nodes || data.nodes.length === 0) {
        console.log('No nodes data');
        return;
    }
    
    console.log(`Updating graph with ${data.nodes.length} nodes, ${data.edges.length} edges`);
    
    // Prepare edges
    const edgeX = [], edgeY = [], edgeZ = [];
    (data.edges || []).forEach(e => {
        edgeX.push(e.x[0], e.x[1], null);
        edgeY.push(e.y[0], e.y[1], null);
        edgeZ.push(e.z[0], e.z[1], null);
    });
    
    // Prepare nodes
    const nodeX = [], nodeY = [], nodeZ = [], labels = [], hoverTexts = [];
    const nodeColors = [], nodeSizes = [];
    
    (data.nodes || []).forEach(n => {
        nodeX.push(n.x);
        nodeY.push(n.y);
        nodeZ.push(n.z);
        labels.push(n.label);
        
        // Enhanced hover text
        let hoverText = `<b>📝 ${n.full || n.label}</b><br>`;
        hoverText += `🏷️ Tags: ${n.tags}<br>`;
        hoverText += `⚡ Urgency: ${n.urgency.toUpperCase()}<br>`;
        hoverText += `🔗 Connections: ${n.degree}<br>`;
        if (n.timestamp) {
            const date = new Date(n.timestamp);
            hoverText += `🕐 ${date.toLocaleString()}<br>`;
        }
        hoverTexts.push(hoverText);
        
        nodeColors.push(n.color);
        nodeSizes.push(Math.max(n.size, 20)); // Ensure minimum size 20
    });
    
    // Generate stars
    const starCount = currentTheme === 'dark' ? 1500 : 600;
    const stars = generateStars(starCount, currentTheme);
    
    // Create traces
    const traces = [
        stars,
        {
            x: edgeX, y: edgeY, z: edgeZ,
            type: 'scatter3d',
            mode: 'lines',
            line: {
                color: currentTheme === 'dark' ? 'rgba(138, 43, 226, 0.7)' : 'rgba(106, 27, 154, 0.6)',
                width: 3
            },
            hoverinfo: 'none',
            showlegend: false
        },
        {
            x: nodeX, y: nodeY, z: nodeZ,
            type: 'scatter3d',
            mode: 'markers+text',
            text: labels,
            textposition: 'top center',
            textfont: {size: 10, color: currentTheme === 'dark' ? 'white' : '#1a1a2e'},
            hovertext: hoverTexts,
            hoverinfo: 'text',
            marker: {
                size: nodeSizes,
                color: nodeColors,
                opacity: 0.95,
                line: {color: 'white', width: 2},
                symbol: 'circle'
            },
            showlegend: false
        }
    ];
    
    const layout = {
        paper_bgcolor: currentTheme === 'dark' ? 'black' : '#f0f0ff',
        plot_bgcolor: currentTheme === 'dark' ? 'black' : '#f0f0ff',
        font: {color: currentTheme === 'dark' ? 'white' : '#1a1a2e'},
        showlegend: false,
        scene: {
            bgcolor: currentTheme === 'dark' ? 'black' : '#f0f0ff',
            xaxis: {showbackground: false, showgrid: false, showticklabels: false, title: '', zeroline: false},
            yaxis: {showbackground: false, showgrid: false, showticklabels: false, title: '', zeroline: false},
            zaxis: {showbackground: false, showgrid: false, showticklabels: false, title: '', zeroline: false},
            camera: {
                eye: {x: 12, y: 8, z: 10},
                up: {x: 0, y: 0, z: 1},
                center: {x: 0, y: 0, z: 0}
            },
            aspectmode: 'manual',
            aspectratio: {x: 1, y: 1, z: 0.8}
        },
        margin: {l: 0, r: 0, t: 0, b: 0},
        hoverlabel: {
            bgcolor: 'rgba(0,0,0,0.8)',
            font: {size: 12, color: 'white'}
        }
    };
    
    Plotly.react('graph', traces, layout, {
        displayModeBar: true,
        displaylogo: false,
        responsive: true,
        modeBarButtonsToRemove: ['lasso2d', 'select2d']
    });
    
    // Update stats
    if (data.stats) {
        document.getElementById('memCount').textContent = data.stats.memories || '-';
        document.getElementById('connCount').textContent = data.stats.connections || '-';
        document.getElementById('avgRelevance').textContent = data.stats.avg_relevance || '-';
        document.getElementById('updateTime').textContent = data.updated_at || '-';
    }
}

function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${location.host}/ws`);
    
    ws.onopen = () => {
        console.log('✅ Connected to WebSocket');
        showToast('🌌 Connected to galaxy');
        document.getElementById('loading').classList.add('hidden');
    };
    
    ws.onclose = () => {
        console.warn('❌ WebSocket disconnected, reconnecting...');
        showToast('🔄 Reconnecting...', true);
        document.getElementById('loading').classList.remove('hidden');
        setTimeout(connectWebSocket, 3000);
    };
    
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.nodes && data.nodes.length > 0) {
                updateGraph(data);
                showToast(`✨ ${data.stats?.memories || 0} memories, ${data.stats?.connections || 0} connections`);
            }
        } catch (err) {
            console.error('Error parsing data:', err);
        }
    };
}

// Initialize
setTimeout(() => {
    connectWebSocket();
}, 1000);
showToast('🌌 Loading galaxy graph...');
</script>
</body>
</html>"""


app = Flask(__name__)
sock = Sock(app)
state = None


@app.route("/")
def index():
    return render_template_string(PAGE_HTML)


@sock.route("/ws")
def websocket(ws):
    with state.lock:
        payload = json.dumps(state.graph_data)
    ws.send(payload)
    state.clients.append(ws)
    try:
        while True:
            ws.receive(timeout=30)
    except Exception:
        pass
    finally:
        try:
            state.clients.remove(ws)
        except ValueError:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    global state
    state = State(args.interval)

    print("🌌 Fetching memories from Membrain API...")
    mems = fetch_all_memories()
    state.graph_data = build_graph_data(mems)
    state._last_count = len(mems)
    print(f"✅ Loaded {len(mems)} memories with {state.graph_data['stats']['connections']} connections")
    print(f"📊 Nodes: {len(state.graph_data['nodes'])}, Edges: {len(state.graph_data['edges'])}")

    threading.Thread(target=state.poll_loop, daemon=True).start()

    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{args.port}")).start()

    print(f"\n🌠 Membrain Galaxy Graph: http://localhost:{args.port}")
    print(f"🔄 Polling every {args.interval}s | 🎮 Ctrl+C to stop\n")
    app.run(host="0.0.0.0", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()