import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";

export default function App() {
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [sessionId, setSessionId] = useState(() => {
    return localStorage.getItem("landtrades_session_id") || "";
  });

  const [messages, setMessages] = useState([
    {
      role: "bot",
      text: "Hello! Ask me about Land Trades projects in Mangalore.",
      sources: [],
      images: [],
    },
  ]);

  const [input, setInput] = useState("");
  const [isListening, setIsListening] = useState(false);

  const [selectedImage, setSelectedImage] = useState(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [expandedImages, setExpandedImages] = useState({});

  const bottomRef = useRef(null);
  const recognitionRef = useRef(null);
  const textareaRef = useRef(null);
  const imageViewportRef = useRef(null);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const touchStateRef = useRef({
    lastDistance: null,
    isPinching: false,
  });

  const copyToClipboard = async (text, index) => {
    try {
      await navigator.clipboard.writeText(text || "");
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 1500);
    } catch (err) {
      console.error("Copy failed", err);
    }
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && selectedImage) {
        closeImageModal();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedImage]);

  useEffect(() => {
    if (!selectedImage || !imageViewportRef.current) return;

    const el = imageViewportRef.current;

    const handleGestureStart = (e) => {
      e.preventDefault();
    };

    const handleGestureChange = (e) => {
      e.preventDefault();
      // Safari trackpad pinch support
      setZoomLevel((prev) => {
        const next = prev * e.scale;
        return Math.min(Math.max(next, 0.5), 6);
      });
    };

    const handleGestureEnd = (e) => {
      e.preventDefault();
    };

    // Safari only
    el.addEventListener("gesturestart", handleGestureStart, { passive: false });
    el.addEventListener("gesturechange", handleGestureChange, { passive: false });
    el.addEventListener("gestureend", handleGestureEnd, { passive: false });

    return () => {
      el.removeEventListener("gesturestart", handleGestureStart);
      el.removeEventListener("gesturechange", handleGestureChange);
      el.removeEventListener("gestureend", handleGestureEnd);
    };
  }, [selectedImage]);

  const streamText = async (text, sources, images) => {
    let i = 0;

    setMessages((prev) => {
      const updated = [...prev];
      updated[updated.length - 1] = {
        role: "bot",
        text: "",
        sources: [],
        images: [],
      };
      return updated;
    });

    const interval = setInterval(() => {
      i++;

      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "bot",
          text: text.slice(0, i),
          sources: i >= text.length ? sources : [],
          images: i >= text.length ? images : [],
        };
        return updated;
      });

      if (i >= text.length) clearInterval(interval);
    }, 8);
  };

  const startVoiceInput = () => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert("Voice recognition not supported in this browser.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;

    recognitionRef.current = recognition;
    setIsListening(true);
    recognition.start();

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setIsListening(false);
      setInput(transcript);
      sendMessage(transcript);
    };

    recognition.onerror = () => {
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };
  };

  const openImageModal = (img) => {
    setSelectedImage(img);
    // Start with fit-to-screen zoom (will be calculated to fit the viewport)
    setZoomLevel(1);
    setPosition({ x: 0, y: 0 });
    setIsDragging(false);
  };

  const closeImageModal = () => {
    setSelectedImage(null);
    setZoomLevel(1);
    setPosition({ x: 0, y: 0 });
    setIsDragging(false);
  };

  const autoResizeTextarea = () => {
    if (!textareaRef.current) return;
    textareaRef.current.style.height = "auto";
    textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
  };

  const clampZoom = (value) => Math.min(Math.max(value, 0.5), 6);

  const handleWheelZoom = (e) => {
    if (!selectedImage) return;

    // Prevent page scroll while interacting with image
    e.preventDefault();

    // Trackpad pinch often appears as ctrl+wheel in Chrome/Edge
    const intensity = e.ctrlKey ? 0.02 : 0.0025;
    const delta = -e.deltaY * intensity;

    setZoomLevel((prev) => clampZoom(prev + delta));
  };

  const handleMouseDown = (e) => {
    if (!selectedImage) return;
    setIsDragging(true);
    dragStartRef.current = {
      x: e.clientX - position.x,
      y: e.clientY - position.y,
    };
  };

  const handleMouseMove = (e) => {
    if (!isDragging) return;

    setPosition({
      x: e.clientX - dragStartRef.current.x,
      y: e.clientY - dragStartRef.current.y,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const getTouchDistance = (touches) => {
    const dx = touches[0].clientX - touches[1].clientX;
    const dy = touches[0].clientY - touches[1].clientY;
    return Math.sqrt(dx * dx + dy * dy);
  };

  const handleTouchStart = (e) => {
    if (e.touches.length === 2) {
      touchStateRef.current.lastDistance = getTouchDistance(e.touches);
      touchStateRef.current.isPinching = true;
    } else if (e.touches.length === 1) {
      touchStateRef.current.isPinching = false;
      setIsDragging(true);
      dragStartRef.current = {
        x: e.touches[0].clientX - position.x,
        y: e.touches[0].clientY - position.y,
      };
    }
  };

  const handleTouchMove = (e) => {
    if (e.touches.length === 2) {
      e.preventDefault();
      const newDistance = getTouchDistance(e.touches);
      const oldDistance = touchStateRef.current.lastDistance;

      if (oldDistance) {
        const scaleFactor = newDistance / oldDistance;
        setZoomLevel((prev) => clampZoom(prev * scaleFactor));
      }

      touchStateRef.current.lastDistance = newDistance;
      touchStateRef.current.isPinching = true;
      return;
    }

    if (e.touches.length === 1 && !touchStateRef.current.isPinching && isDragging) {
      e.preventDefault();
      setPosition({
        x: e.touches[0].clientX - dragStartRef.current.x,
        y: e.touches[0].clientY - dragStartRef.current.y,
      });
    }
  };

  const handleTouchEnd = () => {
    touchStateRef.current.lastDistance = null;
    touchStateRef.current.isPinching = false;
    setIsDragging(false);
  };

  const sendMessage = async (preset = null) => {
    const question = preset || input;
    if (!question.trim()) return;

    const userMessage = {
      role: "user",
      text: question,
    };

    setMessages((prev) => [
      ...prev,
      userMessage,
      { role: "bot", text: "typing...", sources: [], images: [] },
    ]);

    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    try {
      const response = await fetch("http://localhost:8000/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: question,
          session_id: sessionId || null,
        }),
      });

      const raw = await response.json();

      if (raw.session_id && raw.session_id !== sessionId) {
        setSessionId(raw.session_id);
        localStorage.setItem("landtrades_session_id", raw.session_id);
      }

      let answer = "";
      let sources = [];
      let images = [];
      let parsed = raw;

      if (typeof raw === "string") {
        try {
          parsed = JSON.parse(raw);
        } catch {
          parsed = { answer: raw };
        }
      }

      if (parsed.answer && typeof parsed.answer === "object") {
        answer = parsed.answer.answer || "";
        sources = parsed.answer.sources || [];
        images = parsed.answer.images || [];
      } else if (typeof parsed.answer === "string") {
        try {
          const nested = JSON.parse(parsed.answer);
          if (nested.answer) {
            answer = nested.answer;
            sources = nested.sources || parsed.sources || [];
            images = nested.images || parsed.images || [];
          } else {
            answer = parsed.answer;
            sources = parsed.sources || [];
            images = parsed.images || [];
          }
        } catch {
          answer = parsed.answer;
          sources = parsed.sources || [];
          images = parsed.images || [];
        }
      } else {
        answer = "No answer found.";
      }

      answer = answer.replace(/\\n/g, "\n").trim();

      await streamText(answer, sources, images);
    } catch (error) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "bot",
          text: "Server error. Please try again.",
          sources: [],
          images: [],
        };
        return updated;
      });
    }
  };

  const formatMarkdownLists = (text) => {
    if (!text) return "";

    return text
      .replace(/\r\n/g, "\n")
      .replace(/[•✓]/g, "\n- ")
      .replace(/–/g, "\n  - ")
      .replace(/- \*\*Residential Projects:\*\*/g, "\n### Residential Projects")
      .replace(/- \*\*Commercial Projects:\*\*/g, "\n### Commercial Projects")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  };

  const renderImageGrid = (images, messageIndex) => {
    if (!images || images.length === 0) return null;

    const isExpanded = expandedImages[messageIndex];
    const displayedImages = isExpanded ? images : images.slice(0, 4);
    const hasMore = images.length > 4;

    return (
      <div className="mt-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {displayedImages.map((img, i) => (
            <button
              key={i}
              onClick={() => openImageModal(img)}
              className="rounded-xl border bg-gray-50 overflow-hidden shadow-sm text-left hover:shadow-md transition"
            >
              <img
                src={img.url}
                alt={img.label || "Project image"}
                className="w-full h-52 object-cover"
              />
              <div className="p-3">
                <div className="text-sm font-medium text-gray-800">
                  {img.label || "Image"}
                </div>
                {img.category && (
                  <div className="text-xs text-gray-500 mt-1">
                    {img.category}
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>
        {hasMore && !isExpanded && (
          <button
            onClick={() =>
              setExpandedImages((prev) => ({ ...prev, [messageIndex]: true }))
            }
            className="mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium"
          >
            View More ({images.length - 4} more)
          </button>
        )}
        {hasMore && isExpanded && (
          <button
            onClick={() =>
              setExpandedImages((prev) => ({ ...prev, [messageIndex]: false }))
            }
            className="mt-3 px-4 py-2 bg-gray-300 text-gray-800 rounded-lg hover:bg-gray-400 transition text-sm font-medium"
          >
            Show Less
          </button>
        )}
      </div>
    );
  };

  const SideImage = ({ src, alt, caption }) => (
    <div className="relative rounded-xl overflow-hidden shadow-lg h-[500px] transition-transform duration-300 hover:scale-105">
      <img src={src} className="w-full h-full object-cover" alt={alt} />
      <div className="absolute bottom-3 left-3 bg-black/60 text-white px-3 py-1 rounded-md text-sm">
        {caption}
      </div>
    </div>
  );

  return (
    <div className="h-screen w-screen bg-gray-100 flex overflow-hidden">
      {/* LEFT IMAGES */}
      <div className="w-1/5 hidden xl:flex flex-col gap-4 p-4 justify-center">
        <SideImage src="/images/altura.jpg" alt="Altura" caption="Altura" />
        <SideImage
          src="/images/mahalaxmi.jpg"
          alt="Mahalaxmi"
          caption="Mahalaxmi"
        />
      </div>

      {/* CHAT CONTAINER */}
      <div className="flex-1 flex justify-center items-center">
        <div className="w-full max-w-[900px] h-[90vh] bg-white rounded-2xl shadow-xl flex flex-col">
          {/* Header */}
          <div className="p-5 border-b flex items-center gap-4">
            <div className="w-12 h-12 rounded-full overflow-hidden flex items-center justify-center bg-white">
              <img
                src="/images/logo.png"
                alt="Land Trades"
                className="w-10 h-10 object-contain"
              />
            </div>

            <div>
              <h1 className="text-lg font-semibold">Land Trades AI Assistant</h1>
              <p className="text-green-500 text-sm">Mangalore Real Estate</p>
            </div>
          </div>

          {/* Chat Area */}
          <div className="flex-1 p-6 overflow-y-auto bg-gray-50 space-y-6">
            {messages.map((msg, index) => {
              if (msg.role === "user") {
                return (
                  <div key={index} className="flex justify-end">
                    <div className="bg-blue-600 text-white px-4 py-2 rounded-xl max-w-[60%] whitespace-pre-line">
                      {msg.text}
                    </div>
                  </div>
                );
              }

              return (
                <div key={index} className="flex gap-3">
                  <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white">
                    🤖
                  </div>

                  <div className="bg-white border rounded-xl px-4 py-3 shadow-sm max-w-[700px]">
                    <div className="text-gray-800 leading-relaxed">
                      {msg.text === "typing..." ? (
                        <div className="flex gap-1 items-center">
                          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></span>
                          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0.4s]"></span>
                        </div>
                      ) : (
                        <ReactMarkdown
                          components={{
                            a: ({ node, ...props }) => (
                              <a
                                {...props}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-600 underline hover:text-blue-800"
                              />
                            ),
                            p: ({ node, ...props }) => (
                              <p className="mb-2 last:mb-0" {...props} />
                            ),
                            ul: ({ node, ...props }) => (
                              <ul className="list-none ml-0 my-2 space-y-2 pl-0" {...props} />
                            ),
                            ol: ({ node, ...props }) => (
                              <ol className="list-none ml-0 my-2 space-y-2 pl-0" {...props} />
                            ),
                            li: ({ node, children }) => {
                              const depth = node?.position?.start?.column > 3 ? 2 : 1;
                              const symbol = depth === 1 ? "◆" : "▸";
                              const leftPadding = depth === 1 ? "1.5rem" : "0.75rem";

                              return (
                                <li className="relative list-none leading-relaxed" style={{ paddingLeft: leftPadding }}>
                                  <span className="absolute left-0 top-0 text-blue-600">{symbol}</span>
                                  {children}
                                </li>
                              );
                            },
                          }}
                        >
                          {formatMarkdownLists(msg.text || "")}
                        </ReactMarkdown>
                      )}
                    </div>

                    {msg.images &&
                      msg.images.length > 0 &&
                      renderImageGrid(msg.images, index)}

                    {msg.text !== "typing..." && msg.text?.trim() && (
                      <div className="mt-3 flex justify-end">
                        <button
                          onClick={() => copyToClipboard(msg.text, index)}
                          className={`text-xs px-3 py-1 rounded-md border transition-all duration-200 ${
                            copiedIndex === index
                              ? "bg-green-100 text-green-700 border-green-300 scale-105"
                              : "bg-gray-100 text-gray-700 border-gray-200 hover:bg-gray-200"
                          }`}
                        >
                          {copiedIndex === index ? "Copied ✓" : "Copy"}
                        </button>
                      </div>
                    )}

                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-4 text-sm border-t pt-2">
                        <div className="font-semibold text-gray-700 mb-1">
                          Sources
                        </div>

                        {msg.sources.map((s, i) => (
                          <div key={i}>
                            🔗
                            <a
                              href={s.url || s}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:underline ml-1"
                            >
                              {s.title || s.url || s}
                            </a>
                          </div>
                        ))}
                      </div>
                    )}

                    {messages.length === 1 && (
                      <div className="flex flex-col gap-3 mt-3">
                        <div className="flex flex-wrap gap-2">
                          <button
                            onClick={() =>
                              sendMessage("Tell me about Altura project")
                            }
                            className="px-3 py-1 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200"
                          >
                            Altura
                          </button>

                          <button
                            onClick={() =>
                              sendMessage("Tell me about BMK Sky Villa")
                            }
                            className="px-3 py-1 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200"
                          >
                            Sky Villa
                          </button>

                          <button
                            onClick={() =>
                              sendMessage("Tell me about Mahalaxmi project")
                            }
                            className="px-3 py-1 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200"
                          >
                            Mahalaxmi
                          </button>

                          <button
                            onClick={() =>
                              sendMessage("Tell me about Altitude project")
                            }
                            className="px-3 py-1 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200"
                          >
                            Altitude
                          </button>
                        </div>

                        <div className="flex flex-wrap gap-2">
                          <button
                            onClick={() =>
                              sendMessage(
                                "What are the ongoing Land Trades projects?"
                              )
                            }
                            className="px-3 py-1 bg-gray-200 rounded-lg"
                          >
                            Ongoing Projects
                          </button>

                          <button
                            onClick={() =>
                              sendMessage("What amenities are available in Altura?")
                            }
                            className="px-3 py-1 bg-gray-200 rounded-lg"
                          >
                            Amenities in Altura
                          </button>

                          <button
                            onClick={() =>
                              sendMessage(
                                "What are the contact details of Land Trades?"
                              )
                            }
                            className="px-3 py-1 bg-gray-200 rounded-lg"
                          >
                            Contact Details
                          </button>

                          <button
                            onClick={() =>
                              sendMessage("Show Altura 3rd Floor Plan")
                            }
                            className="px-3 py-1 bg-gray-200 rounded-lg"
                          >
                            Altura Floor Plans
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            <div ref={bottomRef}></div>
          </div>

          {/* Input */}
          <div className="p-4 border-t flex gap-3 items-end">
            {isListening && (
              <div className="text-red-500 text-sm mt-1 flex items-center gap-2">
                🎤 Listening...
              </div>
            )}

            <textarea
              ref={textareaRef}
              rows="1"
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                autoResizeTextarea();
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              className="flex-1 border rounded-lg px-4 py-2 outline-none resize-none overflow-hidden"
              placeholder="Ask about Land Trades projects in Mangalore..."
            />

            <div className="flex gap-2">
              <button
                onClick={startVoiceInput}
                className={`px-4 py-2 rounded-lg transition ${
                  isListening
                    ? "bg-red-500 text-white animate-pulse"
                    : "bg-gray-200 hover:bg-gray-300"
                }`}
              >
                🎤
              </button>

              <button
                onClick={() => sendMessage()}
                className="bg-blue-600 text-white px-5 py-2 rounded-lg"
              >
                ➤
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* RIGHT IMAGES */}
      <div className="w-1/5 hidden xl:flex flex-col gap-4 p-4 justify-center">
        <SideImage
          src="/images/skyvilla.jpg"
          alt="Sky Villa"
          caption="BMK Sky Villa"
        />
        <SideImage
          src="/images/altitude.jpg"
          alt="Altitude"
          caption="Altitude"
        />
      </div>

      {/* IMAGE MODAL */}
      {selectedImage && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={closeImageModal}
        >
          <div
            className="relative bg-white rounded-2xl shadow-2xl max-w-6xl w-full max-h-[95vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={closeImageModal}
              className="absolute top-3 right-3 z-10 bg-white/90 hover:bg-white text-gray-800 rounded-full px-3 py-1 shadow"
            >
              ✕
            </button>

            <div className="flex flex-col md:flex-row h-full">
              <div
                ref={imageViewportRef}
                className="flex-1 bg-gray-100 flex items-center justify-center overflow-hidden p-4 cursor-grab active:cursor-grabbing touch-none"
                onWheel={handleWheelZoom}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                onTouchStart={handleTouchStart}
                onTouchMove={handleTouchMove}
                onTouchEnd={handleTouchEnd}
              >
                <img
                  src={selectedImage.url}
                  alt={selectedImage.label || "Project image"}
                  className="select-none pointer-events-none"
                  draggable={false}
                  style={{
                    transform: `translate(${position.x}px, ${position.y}px) scale(${zoomLevel})`,
                    transition: isDragging ? "none" : "transform 0.08s ease-out",
                    maxWidth: "90%",
                    maxHeight: "90%",
                    width: "auto",
                    height: "auto",
                    userSelect: "none",
                  }}
                  onLoad={(e) => {
                    // Auto-calculate zoom level to fit image in viewport on load
                    if (zoomLevel === 1 && imageViewportRef.current) {
                      const viewport = imageViewportRef.current;
                      const img = e.target;
                      
                      const maxWidth = viewport.clientWidth * 0.85;
                      const maxHeight = viewport.clientHeight * 0.85;
                      
                      const scaleX = maxWidth / img.naturalWidth;
                      const scaleY = maxHeight / img.naturalHeight;
                      
                      const fitZoom = Math.min(scaleX, scaleY, 1);
                      if (fitZoom < 1) {
                        setZoomLevel(fitZoom);
                      }
                    }
                  }}
                />
              </div>

              <div className="w-full md:w-80 border-t md:border-t-0 md:border-l bg-white p-4 flex flex-col gap-4">
                <div>
                  <h3 className="text-lg font-semibold text-gray-800">
                    {selectedImage.label || "Image"}
                  </h3>
                  {selectedImage.category && (
                    <p className="text-sm text-gray-500 mt-1">
                      {selectedImage.category}
                    </p>
                  )}
                </div>

                <div className="text-sm text-gray-600">
                  Use mouse wheel, trackpad pinch, or touch pinch to zoom. Drag to move.
                </div>

                <div className="text-sm text-gray-600">
                  Zoom: {(zoomLevel * 100).toFixed(0)}%
                </div>

                {selectedImage.source_url && (
                  <a
                    href={selectedImage.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 underline text-sm"
                  >
                    Open original source
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
