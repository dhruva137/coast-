package `in`.sih26168.idr

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.view.WindowCompat
import `in`.sih26168.idr.ui.IdrApp
import `in`.sih26168.idr.ui.theme.IdrTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        enableEdgeToEdge()
        val bus = (application as IdrApplication).bus
        setContent {
            IdrTheme {
                IdrApp(bus = bus)
            }
        }
    }
}
