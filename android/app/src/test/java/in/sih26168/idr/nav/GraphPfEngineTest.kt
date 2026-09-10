package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.NavMode
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * The graph-PF slot must stay a no-op on JVM / this APK so a later .so can
 * drop in without changing Drive, pairing, or SimpleIns tests.
 */
class GraphPfEngineTest {

    @Test
    fun tryLoadIsNullWithoutNativeLib() {
        assertNull(GraphPfEngine.tryLoad())
    }

    @Test
    fun hudLabelIsRelativeWithoutOrigin() {
        assertEquals(
            GraphPfEngine.LABEL_RELATIVE,
            GraphPfEngine.hudLabel(null, NavMode.RELATIVE),
        )
        assertEquals(
            GraphPfEngine.LABEL_RELATIVE,
            GraphPfEngine.hudLabel(null, NavMode.IDLE),
        )
    }

    @Test
    fun hudLabelIsFreeDrWhenNativeMissing() {
        assertEquals(
            GraphPfEngine.LABEL_FREE_DR,
            GraphPfEngine.hudLabel(null, NavMode.DEAD_RECKONING),
        )
        assertEquals(
            GraphPfEngine.LABEL_FREE_DR,
            GraphPfEngine.hudLabel(null, NavMode.GNSS),
        )
    }
}
