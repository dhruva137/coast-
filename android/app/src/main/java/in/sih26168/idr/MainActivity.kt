package `in`.sih26168.idr

import android.animation.AnimatorSet
import android.animation.ObjectAnimator
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.animation.AccelerateInterpolator
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.WindowCompat
import `in`.sih26168.idr.ui.IdrApp
import `in`.sih26168.idr.ui.theme.IdrTheme

/**
 * Launch is one continuous motion: the system splash paints our own background
 * immediately (no white flash), the mark animates in, and on exit the splash
 * icon scales away while the Compose content fades up underneath it. The two
 * overlap deliberately — the app should read as arriving, not as starting.
 */
class MainActivity : ComponentActivity() {

    /**
     * Held false only until Compose reports its first composition, so the splash
     * covers real initialisation and nothing more. A splash held for effect is
     * the most common way an app is made to feel slow.
     */
    private var uiReady = false

    override fun onCreate(savedInstanceState: Bundle?) {
        val splash = installSplashScreen()
        super.onCreate(savedInstanceState)

        splash.setKeepOnScreenCondition { !uiReady }

        // Safety net: if the first composition never reports in (a broken map
        // surface, a slow device), release the splash anyway rather than
        // stranding the user on it.
        Handler(Looper.getMainLooper()).postDelayed({ uiReady = true }, SPLASH_MAX_HOLD_MS)

        splash.setOnExitAnimationListener { provider ->
            val icon: View = provider.iconView
            AnimatorSet().apply {
                playTogether(
                    ObjectAnimator.ofFloat(icon, View.SCALE_X, 1f, 1.22f),
                    ObjectAnimator.ofFloat(icon, View.SCALE_Y, 1f, 1.22f),
                    ObjectAnimator.ofFloat(icon, View.ALPHA, 1f, 0f),
                    ObjectAnimator.ofFloat(provider.view, View.ALPHA, 1f, 0f),
                )
                duration = EXIT_MS
                interpolator = AccelerateInterpolator(1.4f)
                addListener(
                    object : android.animation.AnimatorListenerAdapter() {
                        override fun onAnimationEnd(animation: android.animation.Animator) {
                            provider.remove()
                        }
                    },
                )
                start()
            }
        }

        WindowCompat.setDecorFitsSystemWindows(window, false)
        enableEdgeToEdge()
        val bus = (application as IdrApplication).bus

        setContent {
            IdrTheme {
                var shown by remember { mutableStateOf(false) }
                // Rises as the splash falls, so the handoff is a cross-fade
                // rather than a cut.
                val fade by animateFloatAsState(
                    targetValue = if (shown) 1f else 0f,
                    animationSpec = tween(durationMillis = ENTER_MS),
                    label = "contentFade",
                )
                LaunchedEffect(Unit) {
                    shown = true
                    uiReady = true
                }
                Box(Modifier.fillMaxSize().alpha(fade)) {
                    IdrApp(bus = bus)
                }
            }
        }
    }

    private companion object {
        const val SPLASH_MAX_HOLD_MS = 1_200L
        const val EXIT_MS = 340L
        const val ENTER_MS = 420
    }
}
