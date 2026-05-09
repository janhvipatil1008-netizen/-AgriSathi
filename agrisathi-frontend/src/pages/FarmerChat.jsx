import { useState, useRef, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'

const API = '/api'

const CROPS = [
  'Cotton', 'Soybean', 'Wheat', 'Rice', 'Onion', 'Tomato',
  'Sugarcane', 'Tur Dal', 'Chickpea', 'Jowar', 'Bajra',
]

const DISTRICTS = [
  'Nagpur', 'Pune', 'Nashik', 'Aurangabad', 'Amravati',
  'Latur', 'Solapur', 'Kolhapur', 'Jalgaon', 'Satara',
  'Akola', 'Yavatmal', 'Nanded', 'Osmanabad', 'Buldhana',
]

const LABELS = {
  en: {
    title: 'AgriSathi',
    subtitle: 'Your Smart Farming Assistant',
    cropLabel: 'Crop',
    districtLabel: 'District',
    placeholder: 'Ask your farming question…',
    send: 'Send',
    thinking: 'AgriSathi is thinking…',
    sources: 'Sources',
    weather: 'Live Weather',
    price: 'Market Price',
    noWeather: 'Weather unavailable',
    noPrice: 'Price unavailable',
    humidity: 'Humidity',
    modal: 'Modal price',
    admin: 'Admin',
    refreshing: 'Refreshing in',
    min: 'min',
  },
  mr: {
    title: 'AgriSathi',
    subtitle: 'तुमचा स्मार्ट शेती सहाय्यक',
    cropLabel: 'पीक',
    districtLabel: 'जिल्हा',
    placeholder: 'तुमचा शेतीविषयक प्रश्न विचारा…',
    send: 'पाठवा',
    thinking: 'AgriSathi विचार करत आहे…',
    sources: 'स्रोत',
    weather: 'थेट हवामान',
    price: 'बाजार भाव',
    noWeather: 'हवामान उपलब्ध नाही',
    noPrice: 'भाव उपलब्ध नाही',
    humidity: 'आर्द्रता',
    modal: 'सामान्य भाव',
    admin: 'Admin',
    refreshing: 'रिफ्रेश',
    min: 'मि',
  },
}

function useInfoCards(crop, district) {
  const [weather, setWeather] = useState(null)
  const [price, setPrice] = useState(null)
  const [countdown, setCountdown] = useState(30 * 60)

  const fetchAll = useCallback(async () => {
    setCountdown(30 * 60)
    try {
      const [wRes, pRes] = await Promise.allSettled([
        fetch(`${API}/weather?district=${encodeURIComponent(district)}`),
        fetch(`${API}/prices?commodity=${encodeURIComponent(crop)}`),
      ])
      if (wRes.status === 'fulfilled' && wRes.value.ok) {
        setWeather(await wRes.value.json())
      } else {
        setWeather(null)
      }
      if (pRes.status === 'fulfilled' && pRes.value.ok) {
        setPrice(await pRes.value.json())
      } else {
        setPrice(null)
      }
    } catch {
      setWeather(null)
      setPrice(null)
    }
  }, [crop, district])

  useEffect(() => {
    fetchAll()
  }, [fetchAll])

  // Countdown tick
  useEffect(() => {
    const id = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) {
          fetchAll()
          return 30 * 60
        }
        return c - 1
      })
    }, 1000)
    return () => clearInterval(id)
  }, [fetchAll])

  const mins = Math.floor(countdown / 60)
  const secs = String(countdown % 60).padStart(2, '0')
  return { weather, price, countdown: `${mins}:${secs}` }
}

export default function FarmerChat() {
  const [lang, setLang] = useState('en')
  const [crop, setCrop] = useState('Cotton')
  const [district, setDistrict] = useState('Nagpur')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)
  const L = LABELS[lang]
  const { weather, price, countdown } = useInfoCards(crop, district)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function sendMessage() {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    setMessages((m) => [...m, { role: 'farmer', text: q }])
    setLoading(true)
    try {
      const res = await fetch(`${API}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: q,
          farmer_context: { crop, district },
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setMessages((m) => [
        ...m,
        {
          role: 'ai',
          text: data.answer,
          sources: data.sources || [],
          language: data.language,
          chunks_used: data.chunks_used,
        },
      ])
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: 'ai', text: `Error: ${err.message}`, sources: [], language: lang },
      ])
    } finally {
      setLoading(false)
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex flex-col h-screen max-w-md mx-auto bg-green-50">
      {/* Header */}
      <header className="bg-green-700 text-white px-4 py-3 flex items-center justify-between shadow-md">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🌾</span>
          <div>
            <div className="font-bold text-lg leading-tight">{L.title}</div>
            <div className="text-green-200 text-xs">{L.subtitle}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Language toggle */}
          <div className="flex rounded-full overflow-hidden border border-green-500 text-sm">
            <button
              onClick={() => setLang('en')}
              className={`px-3 py-1 transition-colors ${lang === 'en' ? 'bg-white text-green-700 font-semibold' : 'text-green-200 hover:bg-green-600'}`}
            >
              EN
            </button>
            <button
              onClick={() => setLang('mr')}
              className={`px-3 py-1 transition-colors ${lang === 'mr' ? 'bg-white text-green-700 font-semibold' : 'text-green-200 hover:bg-green-600'}`}
            >
              मर
            </button>
          </div>
          <Link
            to="/admin"
            className="text-xs text-green-300 hover:text-white border border-green-500 rounded px-2 py-1 transition-colors"
          >
            {L.admin}
          </Link>
        </div>
      </header>

      {/* Farmer profile bar */}
      <div className="bg-green-600 px-4 py-2 flex items-center gap-3">
        <div className="flex items-center gap-1.5 flex-1">
          <label className="text-green-200 text-xs font-medium">{L.cropLabel}</label>
          <select
            value={crop}
            onChange={(e) => setCrop(e.target.value)}
            className="flex-1 bg-green-700 text-white text-sm rounded px-2 py-1 border border-green-500 focus:outline-none focus:ring-1 focus:ring-white"
          >
            {CROPS.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-1.5 flex-1">
          <label className="text-green-200 text-xs font-medium">{L.districtLabel}</label>
          <select
            value={district}
            onChange={(e) => setDistrict(e.target.value)}
            className="flex-1 bg-green-700 text-white text-sm rounded px-2 py-1 border border-green-500 focus:outline-none focus:ring-1 focus:ring-white"
          >
            {DISTRICTS.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3 scrollbar-hide">
        {messages.length === 0 && (
          <div className="text-center text-green-400 text-sm mt-8 select-none">
            <div className="text-4xl mb-3">🌱</div>
            <div>{lang === 'en' ? 'Ask AgriSathi anything about farming…' : 'शेतीबद्दल AgriSathi ला काहीही विचारा…'}</div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'farmer' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'ai' && (
              <div className="w-7 h-7 rounded-full bg-green-600 flex items-center justify-center text-sm mr-2 mt-1 flex-shrink-0">🌾</div>
            )}
            <div className={`max-w-[82%] ${msg.role === 'farmer' ? 'chat-bubble-farmer' : 'chat-bubble-ai'} px-4 py-2.5 text-sm shadow-sm`}>
              <p className="whitespace-pre-wrap leading-relaxed">{msg.text}</p>
              {msg.role === 'ai' && (
                <div className="mt-2 pt-2 border-t border-green-100 flex items-center justify-between gap-2 flex-wrap">
                  {msg.sources?.length > 0 && (
                    <span className="text-xs text-gray-400">
                      {L.sources}: {msg.sources.join(', ')}
                    </span>
                  )}
                  {msg.language && (
                    <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${msg.language === 'mr' ? 'bg-orange-100 text-orange-600' : 'bg-blue-100 text-blue-600'}`}>
                      {msg.language.toUpperCase()}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="w-7 h-7 rounded-full bg-green-600 flex items-center justify-center text-sm mr-2 mt-1 flex-shrink-0">🌾</div>
            <div className="chat-bubble-ai px-4 py-3 text-sm text-green-600 italic shadow-sm">
              <span className="inline-flex gap-1">
                <span className="animate-bounce" style={{ animationDelay: '0ms' }}>•</span>
                <span className="animate-bounce" style={{ animationDelay: '150ms' }}>•</span>
                <span className="animate-bounce" style={{ animationDelay: '300ms' }}>•</span>
              </span>
              <span className="ml-2">{L.thinking}</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Info cards */}
      <div className="px-4 pb-2 grid grid-cols-2 gap-2">
        {/* Weather card */}
        <div className="bg-white rounded-xl p-3 shadow-sm border border-green-100">
          <div className="flex items-center gap-1 text-xs font-semibold text-green-700 mb-1">
            <span>🌤</span> {L.weather}
          </div>
          {weather ? (
            <>
              <div className="text-2xl font-bold text-gray-800">{weather.temp_c?.toFixed(1)}°C</div>
              <div className="text-xs text-gray-500 capitalize">{weather.description}</div>
              <div className="text-xs text-gray-400">{L.humidity}: {weather.humidity}%</div>
              <div className="text-xs text-gray-300 mt-1">{district}</div>
            </>
          ) : (
            <div className="text-xs text-gray-400 mt-1">{L.noWeather}</div>
          )}
        </div>

        {/* Price card */}
        <div className="bg-white rounded-xl p-3 shadow-sm border border-green-100">
          <div className="flex items-center gap-1 text-xs font-semibold text-green-700 mb-1">
            <span>📊</span> {L.price}
          </div>
          {price ? (
            <>
              <div className="text-2xl font-bold text-gray-800">₹{price.modal_price}</div>
              <div className="text-xs text-gray-500">{L.modal}/quintal</div>
              <div className="text-xs text-gray-400">{price.market || crop}</div>
              <div className="text-xs text-gray-300 mt-1">{price.arrival_date}</div>
            </>
          ) : (
            <div className="text-xs text-gray-400 mt-1">{L.noPrice}</div>
          )}
        </div>
      </div>
      <div className="text-center text-xs text-gray-300 pb-1">
        {L.refreshing} {countdown} {L.min}
      </div>

      {/* Input */}
      <div className="px-4 pb-4 pt-2 bg-white border-t border-green-100">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder={L.placeholder}
            rows={1}
            className="flex-1 resize-none rounded-full border border-green-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 bg-green-50"
            style={{ maxHeight: '100px', overflowY: 'auto' }}
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="w-10 h-10 rounded-full bg-green-600 text-white flex items-center justify-center hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex-shrink-0 self-end"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
