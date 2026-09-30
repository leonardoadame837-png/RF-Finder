package com.rfinder.android

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Build
import android.os.Bundle
import android.webkit.CookieManager
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.graphics.Color
import android.view.Gravity
import java.net.Inet4Address

class MainActivity : Activity() {
    companion object {
        private const val SERVICE_TYPE = "_rf-finder._tcp."
        private const val REQUEST_PERMISSIONS = 100
    }

    private lateinit var webView: WebView
    private lateinit var statusText: TextView
    private lateinit var retryButton: Button
    private val mediaPermissions = arrayOf(
        Manifest.permission.CAMERA,
        Manifest.permission.RECORD_AUDIO
    )
    private val prefs by lazy { getSharedPreferences("rf_finder", MODE_PRIVATE) }
    private val nsdManager by lazy { getSystemService(NsdManager::class.java) }
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private val resolving = mutableSetOf<String>()
    private var openedBackend: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val permissions = buildList {
            addAll(mediaPermissions.toList())
            if (Build.VERSION.SDK_INT >= 33) add(Manifest.permission.NEARBY_WIFI_DEVICES)
        }.toTypedArray()
        if (permissions.any { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }) {
            requestPermissions(permissions, REQUEST_PERMISSIONS)
        }
        showConnectScreen()
        startDiscovery()
    }

    private fun showConnectScreen() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 48, 32, 32)
            setBackgroundColor(Color.rgb(5, 10, 17))
        }
        val title = TextView(this).apply {
            text = "RF FINDER"
            textSize = 28f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER_HORIZONTAL
        }
        val help = TextView(this).apply {
            text = "Looking for an RF Finder session on this Wi-Fi network.\n\nYou no longer need to type the laptop IP address."
            textSize = 16f
            setTextColor(Color.LTGRAY)
            setPadding(0, 24, 0, 24)
        }
        statusText = TextView(this).apply {
            text = "Searching for RF Finder…"
            textSize = 15f
            setTextColor(Color.CYAN)
            setPadding(0, 8, 0, 20)
        }
        retryButton = Button(this).apply {
            text = "SEARCH AGAIN"
            isEnabled = false
            setOnClickListener { startDiscovery() }
        }
        val note = TextView(this).apply {
            text = "Camera and microphone data remain camera/audio observations. RF measurements come only from the authenticated RF Finder Spectrum Analyzer."
            textSize = 13f
            setTextColor(Color.GRAY)
            setPadding(0, 24, 0, 0)
        }
        root.addView(title, LinearLayout.LayoutParams(-1, -2))
        root.addView(help, LinearLayout.LayoutParams(-1, -2))
        root.addView(statusText, LinearLayout.LayoutParams(-1, -2))
        root.addView(retryButton, LinearLayout.LayoutParams(-1, -2))
        root.addView(note, LinearLayout.LayoutParams(-1, -2))
        setContentView(root)
    }

    private fun startDiscovery() {
        openedBackend = null
        resolving.clear()
        stopDiscovery()
        statusText.text = "Searching for RF Finder on this Wi-Fi…"
        retryButton.isEnabled = false

        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) {
                runOnUiThread { statusText.text = "Searching for RF Finder on this Wi-Fi…" }
            }

            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                if (!serviceInfo.serviceType.contains("_rf-finder._tcp")) return
                val name = serviceInfo.serviceName
                if (!resolving.add(name)) return

                runOnUiThread { statusText.text = "RF Finder found. Connecting…" }
                nsdManager.resolveService(serviceInfo, object : NsdManager.ResolveListener {
                    override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                        resolving.remove(serviceInfo.serviceName)
                        runOnUiThread {
                            if (openedBackend == null) {
                                statusText.text = "Found RF Finder, but could not resolve it. Searching again…"
                            }
                        }
                    }

                    override fun onServiceResolved(resolved: NsdServiceInfo) {
                        resolving.remove(resolved.serviceName)
                        val ipv4 = resolved.host?.let {
                            if (it is Inet4Address) it.hostAddress else null
                        }
                        if (ipv4 == null || resolved.port <= 0) return

                        val backend = "http://" + ipv4 + ":" + resolved.port
                        if (openedBackend == null) {
                            openedBackend = backend
                            prefs.edit().putString("backend", backend).apply()
                            runOnUiThread {
                                statusText.text = "Connected to RF Finder at " + ipv4 + ":" + resolved.port
                                stopDiscovery()
                                openRfFinder(backend)
                            }
                        }
                    }
                })
            }

            override fun onServiceLost(serviceInfo: NsdServiceInfo) = Unit

            override fun onDiscoveryStopped(serviceType: String) {
                runOnUiThread { retryButton.isEnabled = true }
            }

            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                try { nsdManager.stopServiceDiscovery(this) } catch (_: Exception) {}
                runOnUiThread {
                    statusText.text = "RF Finder discovery failed. Make sure the laptop and phone are on the same Wi-Fi."
                    retryButton.isEnabled = true
                }
            }

            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                runOnUiThread { retryButton.isEnabled = true }
            }
        }

        discoveryListener = listener
        try {
            nsdManager.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, listener)
        } catch (e: Exception) {
            statusText.text = "RF Finder discovery unavailable: " + (e.message ?: "unknown error")
            retryButton.isEnabled = true
        }
    }

    private fun stopDiscovery() {
        discoveryListener?.let {
            try { nsdManager.stopServiceDiscovery(it) } catch (_: IllegalArgumentException) {}
        }
        discoveryListener = null
    }

    private fun openRfFinder(backend: String) {
        webView = WebView(this)
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.settings.mediaPlaybackRequiresUserGesture = false
        webView.settings.allowFileAccess = false
        webView.settings.allowContentAccess = false
        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false)

        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val target = request.url.toString()
                return if (target.startsWith(backend)) {
                    false
                } else {
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(target)))
                    true
                }
            }
        }
        webView.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest) {
                runOnUiThread {
                    if (request.resources.any {
                            it == PermissionRequest.RESOURCE_VIDEO_CAPTURE ||
                            it == PermissionRequest.RESOURCE_AUDIO_CAPTURE
                        }) {
                        request.grant(request.resources)
                    } else {
                        request.deny()
                    }
                }
            }
        }
        setContentView(webView)
        webView.loadUrl(backend + "/camera")
    }

    override fun onDestroy() {
        stopDiscovery()
        super.onDestroy()
    }

    override fun onBackPressed() {
        if (::webView.isInitialized && webView.canGoBack()) webView.goBack()
        else super.onBackPressed()
    }
}
