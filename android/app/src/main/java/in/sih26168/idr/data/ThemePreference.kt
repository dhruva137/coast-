package `in`.sih26168.idr.data

/**
 * Persisted appearance preference (Phase 5.4). Dark is the demo default;
 * light exists and must stay correct without equal polish effort.
 */
enum class ThemePreference {
    System,
    Light,
    Dark,
    ;

    val storageKey: String
        get() = when (this) {
            System -> "system"
            Light -> "light"
            Dark -> "dark"
        }

    companion object {
        fun fromStorage(raw: String?): ThemePreference = when (raw?.lowercase()) {
            "system" -> System
            "light" -> Light
            "dark" -> Dark
            else -> Dark
        }
    }
}
