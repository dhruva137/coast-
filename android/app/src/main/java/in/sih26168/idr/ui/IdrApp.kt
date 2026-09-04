package `in`.sih26168.idr.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.FiberManualRecord
import androidx.compose.material.icons.outlined.Folder
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.Navigation
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.Mute

private val Tabs = listOf("RECORD", "SESSIONS", "NAVIGATE", "ABOUT")

@Composable
fun IdrApp(bus: IdrBus) {
    var tab by rememberSaveable { mutableIntStateOf(0) }
    val (permsOk, request) = rememberPermissionGate()

    Scaffold(
        containerColor = Bg,
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        bottomBar = {
            NavigationBar(
                containerColor = Bg2,
                modifier = Modifier.navigationBarsPadding(),
            ) {
                Tabs.forEachIndexed { i, label ->
                    NavigationBarItem(
                        selected = tab == i,
                        onClick = { tab = i },
                        icon = {
                            Icon(
                                when (i) {
                                    0 -> Icons.Filled.FiberManualRecord
                                    1 -> Icons.Outlined.Folder
                                    2 -> Icons.Outlined.Navigation
                                    else -> Icons.Outlined.Info
                                },
                                contentDescription = label,
                            )
                        },
                        label = {
                            Text(label, fontFamily = IdrMono, fontSize = 10.sp, letterSpacing = 1.sp)
                        },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = Accent,
                            selectedTextColor = Accent,
                            unselectedIconColor = Mute,
                            unselectedTextColor = Mute,
                            indicatorColor = Accent.copy(alpha = 0.16f),
                        ),
                    )
                }
            }
        },
    ) { pad ->
        Column(
            Modifier
                .fillMaxSize()
                .background(Bg)
                .statusBarsPadding()
                .padding(pad),
        ) {
            when (tab) {
                0 -> RecordScreen(bus, permsOk, request)
                1 -> SessionsScreen()
                2 -> NavigateScreen(bus, permsOk, request)
                else -> AboutScreen()
            }
        }
    }
}
