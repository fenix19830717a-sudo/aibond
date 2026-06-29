import React, { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

const Landing: React.FC = () => {
  const navigate = useNavigate();
  const { token } = useAuthStore();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    const particles: { x: number; y: number; vx: number; vy: number; r: number; alpha: number }[] = [];
    const maxParticles = 60;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    for (let i = 0; i < maxParticles; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        r: Math.random() * 2 + 0.5,
        alpha: Math.random() * 0.4 + 0.1,
      });
    }

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach((p, i) => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(22, 119, 255, ${p.alpha})`;
        ctx.fill();

        for (let j = i + 1; j < particles.length; j++) {
          const dx = p.x - particles[j].x;
          const dy = p.y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 120) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(22, 119, 255, ${0.08 * (1 - dist / 120)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      });
      animId = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
    };
  }, []);

  const features = [
    {
      icon: '🌐',
      title: 'MCP 标准化组网',
      desc: '基于 MCP 协议实现跨网络 Agent 通信，支持 WebSocket、SSE、stdio 多种传输方式，打破网络边界。',
    },
    {
      icon: '🏛️',
      title: '议会式协作',
      desc: '多 Agent 议会协商机制，加权投票达成共识，支持提案提交、交叉评审、自动裁决，确保决策质量。',
    },
    {
      icon: '⚡',
      title: 'CLI 本地编排',
      desc: 'Trinity Lite 风格的 CLI 适配器，Pull Queue 原子任务调度，Gate 状态机质量门控，智能模型选择。',
    },
    {
      icon: '🔀',
      title: '可视化工作流',
      desc: '拖拽式工作流编辑器，支持并行节点、Webhook 触发、事件监听，自然语言 Cron 解析，12 种预设模板。',
    },
    {
      icon: '🔐',
      title: '安全可控',
      desc: 'JWT 认证、API Key 鉴权、速率限制、审计日志、安全头（CSP/HSTS），全链路安全防护。',
    },
    {
      icon: '📦',
      title: 'Skills 市场',
      desc: 'Agent Skills 生态，一键安装与发布，MCP 工具注册表，支持 Claude Desktop / Trae IDE 等客户端。',
    },
  ];

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0a0a0f',
      color: '#e0e0e0',
      fontFamily: "'Inter', 'Noto Sans SC', -apple-system, sans-serif",
      overflow: 'hidden',
      position: 'relative',
    }}>
      {/* Particle background */}
      <canvas
        ref={canvasRef}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          zIndex: 0,
        }}
      />

      {/* Navigation */}
      <nav style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 100,
        padding: '16px 32px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: 'rgba(10,10,15,0.85)',
        backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: 'linear-gradient(135deg, #1677ff, #6366f1)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 18, fontWeight: 700, color: '#fff',
          }}>A</div>
          <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: -0.5 }}>aibond</span>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          {token ? (
            <button
              onClick={() => navigate('/app')}
              style={{
                padding: '10px 24px',
                borderRadius: 10,
                border: 'none',
                background: 'linear-gradient(135deg, #1677ff, #6366f1)',
                color: '#fff',
                fontSize: 14,
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = '0 8px 25px rgba(22,119,255,0.35)'; }}
              onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}
            >
              进入工作台
            </button>
          ) : (
            <>
              <button
                onClick={() => navigate('/login')}
                style={{
                  padding: '10px 24px',
                  borderRadius: 10,
                  border: '1px solid rgba(255,255,255,0.15)',
                  background: 'transparent',
                  color: '#e0e0e0',
                  fontSize: 14,
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.35)'; e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)'; e.currentTarget.style.background = 'transparent'; }}
              >
                登录
              </button>
              <button
                onClick={() => navigate('/login')}
                style={{
                  padding: '10px 24px',
                  borderRadius: 10,
                  border: 'none',
                  background: 'linear-gradient(135deg, #1677ff, #6366f1)',
                  color: '#fff',
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = '0 8px 25px rgba(22,119,255,0.35)'; }}
                onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}
              >
                免费注册
              </button>
            </>
          )}
        </div>
      </nav>

      {/* Hero Section */}
      <section style={{
        position: 'relative',
        zIndex: 10,
        padding: '160px 32px 80px',
        textAlign: 'center',
        maxWidth: 900,
        margin: '0 auto',
      }}>
        <div style={{
          display: 'inline-block',
          padding: '6px 16px',
          borderRadius: 20,
          background: 'rgba(22,119,255,0.1)',
          border: '1px solid rgba(22,119,255,0.2)',
          fontSize: 13,
          color: '#1677ff',
          marginBottom: 32,
          fontWeight: 500,
        }}>
          v1.4.0 · 企业级人机协同路由平台
        </div>

        <h1 style={{
          fontSize: 'clamp(40px, 7vw, 72px)',
          fontWeight: 800,
          lineHeight: 1.1,
          margin: '0 0 24px',
          background: 'linear-gradient(135deg, #ffffff 0%, #a0a0c0 50%, #1677ff 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          letterSpacing: -1.5,
        }}>
          跨网络 Agent
          <br />
          通信与协作平台
        </h1>

        <p style={{
          fontSize: 18,
          color: '#888',
          maxWidth: 600,
          margin: '0 auto 48px',
          lineHeight: 1.7,
        }}>
          让分布在不同网络、不同环境的 AI Agent 通过 MCP 协议无缝互联。
          支持议会式协商、CLI 本地编排、可视化工作流，
          构建企业级多 Agent 协作网络。
        </p>

        <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
          {token ? (
            <button
              onClick={() => navigate('/app')}
              style={{
                padding: '16px 40px',
                borderRadius: 14,
                border: 'none',
                background: 'linear-gradient(135deg, #1677ff, #6366f1)',
                color: '#fff',
                fontSize: 16,
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 12px 35px rgba(22,119,255,0.4)'; }}
              onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}
            >
              进入工作台 →
            </button>
          ) : (
            <button
              onClick={() => navigate('/login')}
              style={{
                padding: '16px 40px',
                borderRadius: 14,
                border: 'none',
                background: 'linear-gradient(135deg, #1677ff, #6366f1)',
                color: '#fff',
                fontSize: 16,
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 12px 35px rgba(22,119,255,0.4)'; }}
              onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}
            >
              免费开始使用 →
            </button>
          )}
          <a
            href="https://github.com/fenix19830717a-sudo/aibond"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              padding: '16px 40px',
              borderRadius: 14,
              border: '1px solid rgba(255,255,255,0.15)',
              background: 'transparent',
              color: '#e0e0e0',
              fontSize: 16,
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'all 0.2s',
              textDecoration: 'none',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.35)'; e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)'; e.currentTarget.style.background = 'transparent'; }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
            </svg>
            GitHub
          </a>
        </div>

        {/* Stats */}
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          gap: 64,
          marginTop: 80,
          paddingTop: 48,
          borderTop: '1px solid rgba(255,255,255,0.06)',
        }}>
          {[
            { value: 'MCP', label: '标准化协议' },
            { value: 'WebSocket', label: '跨网络通信' },
            { value: '11 状态', label: 'Gate 门控' },
            { value: '15+', label: 'API 端点' },
          ].map((stat, i) => (
            <div key={i} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 28, fontWeight: 800, color: '#1677ff', letterSpacing: -0.5 }}>{stat.value}</div>
              <div style={{ fontSize: 13, color: '#666', marginTop: 4 }}>{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features Section */}
      <section style={{
        position: 'relative',
        zIndex: 10,
        padding: '80px 32px 120px',
        maxWidth: 1100,
        margin: '0 auto',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 64 }}>
          <h2 style={{
            fontSize: 36,
            fontWeight: 800,
            letterSpacing: -0.5,
            margin: '0 0 12px',
            color: '#fff',
          }}>
            核心能力
          </h2>
          <p style={{ fontSize: 16, color: '#777', maxWidth: 500, margin: '0 auto' }}>
            从通信到协作，从编排到治理，aibond 为多 Agent 系统提供完整的基础设施
          </p>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: 20,
        }}>
          {features.map((f, i) => (
            <div
              key={i}
              style={{
                padding: '32px',
                borderRadius: 16,
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)',
                transition: 'all 0.3s',
                cursor: 'default',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
                e.currentTarget.style.borderColor = 'rgba(22,119,255,0.25)';
                e.currentTarget.style.transform = 'translateY(-4px)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
            >
              <div style={{ fontSize: 36, marginBottom: 16 }}>{f.icon}</div>
              <h3 style={{ fontSize: 18, fontWeight: 700, margin: '0 0 8px', color: '#fff' }}>{f.title}</h3>
              <p style={{ fontSize: 14, color: '#888', lineHeight: 1.7, margin: 0 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Architecture Section */}
      <section style={{
        position: 'relative',
        zIndex: 10,
        padding: '80px 32px 120px',
        maxWidth: 1100,
        margin: '0 auto',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 64 }}>
          <h2 style={{ fontSize: 36, fontWeight: 800, letterSpacing: -0.5, margin: '0 0 12px', color: '#fff' }}>
            架构概览
          </h2>
          <p style={{ fontSize: 16, color: '#777' }}>多层架构，模块化设计，开放协议</p>
        </div>

        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          maxWidth: 700,
          margin: '0 auto',
        }}>
          {[
            { label: '接入层', desc: 'WebSocket · SSE · CLI · Webhook', color: '#1677ff' },
            { label: '通信层', desc: 'MCP Protocol · Message Routing · Transport', color: '#6366f1' },
            { label: '协作层', desc: 'Parliament 议会 · Workflow 工作流 · Pull Queue', color: '#8b5cf6' },
            { label: '治理层', desc: 'Gate 门控 · Audit 审计 · Auth 鉴权 · Rate Limit', color: '#a855f7' },
            { label: '数据层', desc: 'PostgreSQL · SQLite · Redis', color: '#c084fc' },
          ].map((layer, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 20,
                padding: '20px 28px',
                borderRadius: 12,
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)',
                transition: 'all 0.2s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = `${layer.color}44`;
                e.currentTarget.style.background = 'rgba(255,255,255,0.05)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)';
                e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
              }}
            >
              <div style={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: layer.color,
                boxShadow: `0 0 12px ${layer.color}66`,
                flexShrink: 0,
              }} />
              <div style={{ fontWeight: 700, fontSize: 15, color: '#fff', minWidth: 70 }}>{layer.label}</div>
              <div style={{ color: '#666', fontSize: 13, flex: 1 }}>{layer.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA Section */}
      <section style={{
        position: 'relative',
        zIndex: 10,
        padding: '0 32px 120px',
        textAlign: 'center',
      }}>
        <div style={{
          maxWidth: 600,
          margin: '0 auto',
          padding: '64px 48px',
          borderRadius: 24,
          background: 'linear-gradient(135deg, rgba(22,119,255,0.08), rgba(99,102,241,0.08))',
          border: '1px solid rgba(22,119,255,0.15)',
        }}>
          <h2 style={{ fontSize: 32, fontWeight: 800, margin: '0 0 12px', color: '#fff', letterSpacing: -0.5 }}>
            开始构建你的 Agent 网络
          </h2>
          <p style={{ fontSize: 16, color: '#888', margin: '0 0 32px', lineHeight: 1.6 }}>
            免费注册，即刻连接你的第一个 AI Agent。支持 Claude Desktop、Trae IDE 等主流客户端。
          </p>
          {!token && (
            <button
              onClick={() => navigate('/login')}
              style={{
                padding: '16px 48px',
                borderRadius: 14,
                border: 'none',
                background: 'linear-gradient(135deg, #1677ff, #6366f1)',
                color: '#fff',
                fontSize: 16,
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 12px 35px rgba(22,119,255,0.4)'; }}
              onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}
            >
              免费注册 →
            </button>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer style={{
        position: 'relative',
        zIndex: 10,
        padding: '32px',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        textAlign: 'center',
      }}>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 32, marginBottom: 16 }}>
          <a href="https://github.com/fenix19830717a-sudo/aibond" target="_blank" rel="noopener noreferrer" style={{ color: '#666', fontSize: 13, textDecoration: 'none' }}
            onMouseEnter={e => { e.currentTarget.style.color = '#1677ff'; }}
            onMouseLeave={e => { e.currentTarget.style.color = '#666'; }}
          >GitHub</a>
          <span style={{ color: '#666', fontSize: 13 }}>MCP Registry</span>
          <span style={{ color: '#666', fontSize: 13 }}>Apache 2.0</span>
        </div>
        <div style={{ color: '#444', fontSize: 12 }}>© 2026 aibond. All rights reserved.</div>
      </footer>
    </div>
  );
};

export default Landing;