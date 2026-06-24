import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock import.meta.env
vi.stubGlobal('import.meta', {
  env: {
    VITE_API_BASE: 'http://localhost:8000',
  },
});

// We need to mock localStorage and fetch before importing the api module
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock });

// Mock window.location
const mockLocation = { href: '' };
Object.defineProperty(globalThis, 'window', {
  value: {
    ...globalThis.window,
    location: mockLocation,
  },
});

// Must import AFTER mocks are set up
const { api } = await import('../api/index');

describe('API module', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
    mockLocation.href = '';

    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('should include Authorization header when token exists', async () => {
    localStorageMock.setItem('aibond_token', 'test-token-123');

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ data: 'ok' }),
    });

    await api.listGroups();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/groups/');
    expect(options.headers['Authorization']).toBe('Bearer test-token-123');
    expect(options.headers['Content-Type']).toBe('application/json');
  });

  it('should NOT include Authorization header when token is absent', async () => {
    // localStorage is empty, so getToken() returns null
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ data: 'ok' }),
    });

    await api.listGroups();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers['Authorization']).toBeUndefined();
  });

  it('should clear auth state and redirect on 401 response', async () => {
    localStorageMock.setItem('aibond_token', 'expired-token');
    localStorageMock.setItem('aibond_user', JSON.stringify({ id: '1' }));

    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ detail: 'Unauthorized' }),
    });

    await expect(api.listGroups()).rejects.toThrow('登录已过期，请重新登录');

    expect(localStorageMock.removeItem).toHaveBeenCalledWith('aibond_token');
    expect(localStorageMock.removeItem).toHaveBeenCalledWith('aibond_user');
    expect(mockLocation.href).toBe('/login');
  });

  it('should throw rate limit error on 429 response', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 429,
      json: () => Promise.resolve({ detail: '' }),
    });

    await expect(api.listGroups()).rejects.toThrow('请求过于频繁，请稍后再试');
  });

  it('should throw generic error detail on non-ok response', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: 'Internal Server Error' }),
    });

    await expect(api.listGroups()).rejects.toThrow('Internal Server Error');
  });

  it('should throw default message when error response has no detail', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error('parse error')),
    });

    await expect(api.listGroups()).rejects.toThrow('Request failed');
  });

  it('should send POST request with JSON body for login', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ token: 'new-token' }),
    });

    await api.login('testuser', 'password123');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/auth/login');
    expect(options.method).toBe('POST');
    expect(options.body).toBe(JSON.stringify({ username: 'testuser', password: 'password123' }));
  });

  it('should send GET request for listAgents with status query param', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ agents: [] }),
    });

    await api.listAgents('online');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/agents/?status=online');
  });
});
