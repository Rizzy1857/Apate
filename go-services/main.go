// Go HTTP Server - IoT Device Emulator
// ------------------------------------
// Simulates IoT devices with realistic endpoints and responses.
// Includes adaptive behavior and threat detection capabilities.

package main

import (
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"
)

// DeviceInfo represents an IoT device
type DeviceInfo struct {
	DeviceID     string    `json:"device_id"`
	DeviceType   string    `json:"device_type"`
	Model        string    `json:"model"`
	Firmware     string    `json:"firmware"`
	Status       string    `json:"status"`
	LastSeen     time.Time `json:"last_seen"`
	IPAddress    string    `json:"ip_address"`
	MACAddress   string    `json:"mac_address"`
	Uptime       int64     `json:"uptime_seconds"`
}

// CameraStream represents camera streaming data
type CameraStream struct {
	StreamID    string `json:"stream_id"`
	Resolution  string `json:"resolution"`
	FPS         int    `json:"fps"`
	Quality     string `json:"quality"`
	Status      string `json:"status"`
	ViewerCount int    `json:"viewer_count"`
}

// ThreatEvent represents a security event
type ThreatEvent struct {
	EventID     string                 `json:"event_id"`
	Timestamp   time.Time              `json:"timestamp"`
	SourceIP    string                 `json:"source_ip"`
	EventType   string                 `json:"event_type"`
	Description string                 `json:"description"`
	Severity    string                 `json:"severity"`
	Metadata    map[string]interface{} `json:"metadata"`
}

// Server holds the IoT device server state
type Server struct {
	devices      map[string]*DeviceInfo
	streams      map[string]*CameraStream
	threats      []ThreatEvent
	startTime    time.Time
	accessAttempts map[string][]time.Time
	mutex        sync.RWMutex
}

// NewServer creates a new IoT server instance
func NewServer() *Server {
	server := &Server{
		devices:        make(map[string]*DeviceInfo),
		streams:        make(map[string]*CameraStream),
		threats:        make([]ThreatEvent, 0),
		startTime:      time.Now(),
		accessAttempts: make(map[string][]time.Time),
	}
	
	// Initialize some fake devices
	server.initializeDevices()
	server.initializeStreams()
	
	return server
}

// Initialize fake IoT devices
func (s *Server) initializeDevices() {
	devices := []DeviceInfo{
		{
			DeviceID:   "cam-001",
			DeviceType: "security_camera",
			Model:      "SecureCam Pro X1",
			Firmware:   "v2.4.1",
			Status:     "online",
			LastSeen:   time.Now(),
			IPAddress:  "192.168.1.101",
			MACAddress: "aa:bb:cc:dd:ee:01",
			Uptime:     int64(time.Since(time.Now().Add(-24 * time.Hour)).Seconds()),
		},
		{
			DeviceID:   "cam-002", 
			DeviceType: "security_camera",
			Model:      "WatchGuard 4K",
			Firmware:   "v1.8.3",
			Status:     "online",
			LastSeen:   time.Now(),
			IPAddress:  "192.168.1.102",
			MACAddress: "aa:bb:cc:dd:ee:02",
			Uptime:     int64(time.Since(time.Now().Add(-48 * time.Hour)).Seconds()),
		},
		{
			DeviceID:   "sensor-001",
			DeviceType: "temperature_sensor",
			Model:      "TempSense IoT",
			Firmware:   "v3.1.0",
			Status:     "online",
			LastSeen:   time.Now(),
			IPAddress:  "192.168.1.201",
			MACAddress: "aa:bb:cc:dd:ee:03",
			Uptime:     int64(time.Since(time.Now().Add(-72 * time.Hour)).Seconds()),
		},
	}
	
	for _, device := range devices {
		deviceCopy := device
		s.devices[device.DeviceID] = &deviceCopy
	}
}

// Initialize fake camera streams
func (s *Server) initializeStreams() {
	streams := []CameraStream{
		{
			StreamID:    "stream-001",
			Resolution:  "1920x1080",
			FPS:         30,
			Quality:     "high",
			Status:      "active",
			ViewerCount: rand.Intn(5),
		},
		{
			StreamID:    "stream-002",
			Resolution:  "1280x720", 
			FPS:         15,
			Quality:     "medium",
			Status:      "active",
			ViewerCount: rand.Intn(3),
		},
	}
	
	for _, stream := range streams {
		streamCopy := stream
		s.streams[stream.StreamID] = &streamCopy
	}
}

// Track access attempts for rate limiting and threat detection
func (s *Server) trackAccess(ip string) bool {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	
	now := time.Now()
	
	// Clean old attempts (older than 1 minute)
	if attempts, exists := s.accessAttempts[ip]; exists {
		var validAttempts []time.Time
		for _, attempt := range attempts {
			if now.Sub(attempt) < time.Minute {
				validAttempts = append(validAttempts, attempt)
			}
		}
		s.accessAttempts[ip] = validAttempts
	}
	
	// Add current attempt
	if s.accessAttempts[ip] == nil {
		s.accessAttempts[ip] = make([]time.Time, 0)
	}
	s.accessAttempts[ip] = append(s.accessAttempts[ip], now)
	
	// Check if rate limit exceeded
	if len(s.accessAttempts[ip]) > 10 {
		s.logThreatEvent(ip, "rate_limit_exceeded", "Too many requests", "medium")
		return false
	}
	
	return true
}

// Log threat events
func (s *Server) logThreatEvent(sourceIP, eventType, description, severity string) {
	event := ThreatEvent{
		EventID:     fmt.Sprintf("evt_%d", time.Now().Unix()),
		Timestamp:   time.Now(),
		SourceIP:    sourceIP,
		EventType:   eventType,
		Description: description,
		Severity:    severity,
		Metadata:    make(map[string]interface{}),
	}
	
	s.mutex.Lock()
	s.threats = append(s.threats, event)
	s.mutex.Unlock()
	
	log.Printf("THREAT EVENT: %s from %s - %s", eventType, sourceIP, description)
}

// Middleware for request logging and basic security
func (s *Server) securityMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		clientIP := r.Header.Get("X-Forwarded-For")
		if clientIP == "" {
			clientIP = strings.Split(r.RemoteAddr, ":")[0]
		}
		
		// Log request
		log.Printf("Request: %s %s from %s", r.Method, r.URL.Path, clientIP)
		
		// Check rate limiting
		if !s.trackAccess(clientIP) {
			http.Error(w, "Rate limit exceeded", http.StatusTooManyRequests)
			return
		}
		
		// Check for suspicious user agents
		userAgent := r.Header.Get("User-Agent")
		suspiciousAgents := []string{"curl", "wget", "python", "scanner", "bot", "nmap"}
		for _, agent := range suspiciousAgents {
			if strings.Contains(strings.ToLower(userAgent), agent) {
				s.logThreatEvent(clientIP, "suspicious_user_agent", fmt.Sprintf("Suspicious user agent: %s", userAgent), "low")
				break
			}
		}
		
		// Check for common attack paths
		suspiciousPaths := []string{"/admin", "/config", "/setup", "/.env", "/backup"}
		for _, path := range suspiciousPaths {
			if strings.Contains(strings.ToLower(r.URL.Path), path) {
				s.logThreatEvent(clientIP, "suspicious_path_access", fmt.Sprintf("Access to suspicious path: %s", r.URL.Path), "medium")
				break
			}
		}
		
		// Add security headers
		w.Header().Set("Server", "IoT-Gateway/1.2.3")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		
		next(w, r)
	}
}

// Root handler - device information
func (s *Server) rootHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	
	response := map[string]interface{}{
		"service": "IoT Device Gateway",
		"version": "1.2.3",
		"status":  "online",
		"uptime":  int64(time.Since(s.startTime).Seconds()),
		"devices": len(s.devices),
		"streams": len(s.streams),
	}
	
	json.NewEncoder(w).Encode(response)
}

// Camera endpoint - main honeypot target
func (s *Server) cameraHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	
	// Extract camera ID if provided
	cameraID := r.URL.Query().Get("id")
	if cameraID == "" {
		cameraID = "cam-001" // default camera
	}
	
	// Check if device exists
	device, exists := s.devices[cameraID]
	if !exists {
		http.Error(w, "Camera not found", http.StatusNotFound)
		return
	}
	
	// Simulate camera stream data
	response := map[string]interface{}{
		"camera_id":    device.DeviceID,
		"model":        device.Model,
		"status":       device.Status,
		"stream_url":   fmt.Sprintf("rtsp://192.168.1.101:554/stream/%s", cameraID),
		"snapshot_url": fmt.Sprintf("http://192.168.1.101:8080/snapshot/%s.jpg", cameraID),
		"resolution":   "1920x1080",
		"fps":          30,
		"last_motion":  time.Now().Add(-time.Duration(rand.Intn(300)) * time.Second),
		"recording":    true,
		"night_vision": rand.Intn(2) == 1,
		"audio":        true,
	}
	
	json.NewEncoder(w).Encode(response)
}

// Devices list endpoint
func (s *Server) devicesHandler(w http.ResponseWriter, r *http.Request) {
	s.mutex.RLock()
	defer s.mutex.RUnlock()
	
	w.Header().Set("Content-Type", "application/json")
	
	var deviceList []DeviceInfo
	for _, device := range s.devices {
		deviceList = append(deviceList, *device)
	}
	
	response := map[string]interface{}{
		"total_devices": len(deviceList),
		"devices":      deviceList,
	}
	
	json.NewEncoder(w).Encode(response)
}

// Stream endpoint
func (s *Server) streamHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	
	streamID := r.URL.Query().Get("id")
	if streamID == "" {
		// Return all streams
		s.mutex.RLock()
		var streamList []CameraStream
		for _, stream := range s.streams {
			streamList = append(streamList, *stream)
		}
		s.mutex.RUnlock()
		
		json.NewEncoder(w).Encode(map[string]interface{}{
			"streams": streamList,
		})
		return
	}
	
	// Return specific stream
	stream, exists := s.streams[streamID]
	if !exists {
		http.Error(w, "Stream not found", http.StatusNotFound)
		return
	}
	
	json.NewEncoder(w).Encode(stream)
}

// Config endpoint (honeypot target)
func (s *Server) configHandler(w http.ResponseWriter, r *http.Request) {
	clientIP := strings.Split(r.RemoteAddr, ":")[0]
	s.logThreatEvent(clientIP, "config_access_attempt", "Attempt to access configuration", "high")
	
	// Return fake configuration that looks real but contains honeytokens
	w.Header().Set("Content-Type", "application/json")
	
	fakeConfig := map[string]interface{}{
		"device_name": "IoT-Gateway-Main",
		"network": map[string]interface{}{
			"wifi_ssid":     "IoT_Network_5G",
			"wifi_password": "IoT_Secure_2023!",
			"ip_range":      "192.168.1.0/24",
		},
		"admin": map[string]interface{}{
			"username": "admin",
			"password": "IoT_Admin_Pass123!",
			"api_key":  "iot_api_key_" + strconv.FormatInt(time.Now().Unix(), 10),
		},
		"cloud": map[string]interface{}{
			"enabled":    true,
			"endpoint":   "https://cloud.iot-gateway.com",
			"auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake_honeytoken_jwt.signature",
		},
		"backup": map[string]interface{}{
			"ftp_host":     "backup.internal.local",
			"ftp_user":     "backup_service",
			"ftp_password": "Backup_FTP_2023!",
		},
	}
	
	json.NewEncoder(w).Encode(fakeConfig)
}

// Admin endpoint (major honeypot target)
func (s *Server) adminHandler(w http.ResponseWriter, r *http.Request) {
	clientIP := strings.Split(r.RemoteAddr, ":")[0]
	s.logThreatEvent(clientIP, "admin_access_attempt", "Attempt to access admin interface", "critical")
	
	w.Header().Set("Content-Type", "text/html")
	
	// Return fake admin login page
	adminPage := `<!DOCTYPE html>
<html>
<head>
    <title>IoT Gateway Admin Panel</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .login-box { background: white; padding: 20px; border-radius: 5px; max-width: 400px; margin: auto; }
        input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; }
        button { background: #007cba; color: white; padding: 10px 20px; border: none; cursor: pointer; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>IoT Gateway Admin Panel</h2>
        <form method="post" action="/admin/login">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
        <p><small>IoT Gateway v1.2.3 | Build 20230824</small></p>
    </div>
</body>
</html>`
	
	w.Write([]byte(adminPage))
}

// Status endpoint
func (s *Server) statusHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	
	s.mutex.RLock()
	threatCount := len(s.threats)
	s.mutex.RUnlock()
	
	response := map[string]interface{}{
		"status":         "healthy",
		"uptime_seconds": int64(time.Since(s.startTime).Seconds()),
		"devices_online": len(s.devices),
		"active_streams": len(s.streams),
		"threat_events":  threatCount,
		"memory_usage":   "45%",
		"cpu_usage":      "12%",
		"last_restart":   s.startTime.Format(time.RFC3339),
	}
	
	json.NewEncoder(w).Encode(response)
}

// Threats endpoint (for monitoring)
func (s *Server) threatsHandler(w http.ResponseWriter, r *http.Request) {
	s.mutex.RLock()
	defer s.mutex.RUnlock()
	
	w.Header().Set("Content-Type", "application/json")
	
	// Return last 50 threat events
	var recentThreats []ThreatEvent
	start := len(s.threats) - 50
	if start < 0 {
		start = 0
	}
	
	recentThreats = s.threats[start:]
	
	response := map[string]interface{}{
		"total_threats":  len(s.threats),
		"recent_threats": recentThreats,
	}
	
	json.NewEncoder(w).Encode(response)
}

func main() {
	server := NewServer()
	
	// Set up routes with security middleware
	http.HandleFunc("/", server.securityMiddleware(server.rootHandler))
	http.HandleFunc("/camera", server.securityMiddleware(server.cameraHandler))
	http.HandleFunc("/devices", server.securityMiddleware(server.devicesHandler))
	http.HandleFunc("/stream", server.securityMiddleware(server.streamHandler))
	http.HandleFunc("/config", server.securityMiddleware(server.configHandler))
	http.HandleFunc("/admin", server.securityMiddleware(server.adminHandler))
	http.HandleFunc("/status", server.securityMiddleware(server.statusHandler))
	http.HandleFunc("/threats", server.securityMiddleware(server.threatsHandler))
	
	port := ":8081"
	log.Printf("IoT Device Gateway starting on port %s", port)
	log.Printf("Main endpoint: http://localhost%s/camera", port)
	log.Printf("Admin interface: http://localhost%s/admin", port)
	log.Printf("Device list: http://localhost%s/devices", port)
	
	if err := http.ListenAndServe(port, nil); err != nil {
		log.Fatal("Server failed to start:", err)
	}
}
