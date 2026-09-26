package com.rfinder.android

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.webkit.CookieManager
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.Button
import android.widget.TextView
import android.graphics.Color
import android.view.ViewGroup
import android.view.Gravity

class MainActivity : Activity() {
    private lateinit var webView: WebView
    private val requiredPermissions = arrayOf(
        Manifest.permission.CAMERA,
        Manifest.permission.RECORD_AUDIO
    )
    private val prefs by lazy { getSharedPreferences("rf_finder", MODE_PRIVATE) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!hasPermissions()) requestPermissions(requiredPermissions, 100)
        showConnectScreen()
    }

    private fun hasPermissions(): Boolean =
        requiredPermissions.all { checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED }

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
            text = "Connect to the RF Finder session running on your laptop.\n\nBoth devices must be on the same Wi-Fi network."
            textSize = 16f
            setTextColor(Color.LTGRAY)
            setPadding(0, 24, 0, 24)
        }
        val host = EditText(this).apply {
            hint = "Laptop address, e.g. 192.168.1.84:8000"
            setText(prefs.getString("backend", ""))
            setTextColor(Color.WHITE)
            setHintTextColor(Color.GRAY)
            setSingleLine(true)
        }
        val connect = Button(this).apply {
            text = "CONNECT TO RF FINDER"
            setOnClickListener {
                val raw = host.text.toString().trim()
                val normalized = when {
                    raw.startsWith("http://") || raw.startsWith("https://") -> raw
                    else -> "http://$raw"
                }.removeSuffix("/")
                if (normalized.isNotBlank()) {
                    prefs.edit().putString("backend", normalized).apply()
                    openRfFinder(normalized)
                }
            }
        }
        val note = TextView(this).apply {
            text = "Camera and microphone data remain camera/audio observations. RF measurements come only from the authenticated RF Finder Spectrum Analyzer."
            textSize = 13f
            setTextColor(Color.GRAY)
            setPadding(0, 24, 0, 0)
        }
        root.addView(title, LinearLayout.LayoutParams(-1, -2))
        root.addView(help, LinearLayout.LayoutParams(-1, -2))
        root.addView(host, LinearLayout.LayoutParams(-1, -2))
        root.addView(connect, LinearLayout.LayoutParams(-1, -2))
        root.addView(note, LinearLayout.LayoutParams(-1, -2))
        setContentView(root)
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
                    if (request.resources.any { it == PermissionRequest.RESOURCE_VIDEO_CAPTURE || it == PermissionRequest.RESOURCE_AUDIO_CAPTURE }) {
                        request.grant(request.resources)
                    } else {
                        request.deny()
                    }
                }
            }
        }
        setContentView(webView)
        webView.loadUrl("$backend/camera")
    }

    override fun onBackPressed() {
        if (::webView.isInitialized && webView.canGoBack()) webView.goBack()
        else super.onBackPressed()
    }
}
