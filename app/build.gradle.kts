plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

android {
    namespace = "com.lizongying.mytv0"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.lizongying.newmytv"
        minSdk = 21
        targetSdk = 35
        versionCode = 33751040
        versionName = "2.3.0"
    }

    flavorDimensions += "language"
    productFlavors {
        create("zh") {
            dimension = "language"
            buildConfigField("int", "SERVER_PORT", "34567")
        }
        create("en") {
            dimension = "language"
            applicationIdSuffix = ".en"
            buildConfigField("int", "SERVER_PORT", "34568")
        }
    }

    buildFeatures {
        buildConfig = true
        viewBinding = true
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        // Flag to enable support for the new language APIs
        // For AGP 4.1+
        isCoreLibraryDesugaringEnabled = true

        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
    kotlinOptions {
        jvmTarget = "1.8"
    }
}

dependencies {
    // For AGP 7.4+
    coreLibraryDesugaring(libs.desugar.jdk.libs)

    implementation(libs.media3.ui)
    implementation(libs.media3.exoplayer)
    implementation(libs.media3.exoplayer.hls)
    implementation(libs.media3.exoplayer.dash)
    implementation(libs.media3.exoplayer.rtsp)
    implementation(libs.media3.datasource.okhttp)
    implementation(libs.media3.datasource.rtmp)

    implementation(libs.nanohttpd)
    implementation(libs.gua64)
    implementation(libs.zxing)
    implementation(libs.glide)

    implementation(libs.gson)
    implementation(libs.okhttp)

    implementation(libs.core.ktx)
    implementation(libs.coroutines)

    implementation(libs.constraintlayout)
    implementation(libs.appcompat)
    implementation(libs.recyclerview)
    implementation(libs.lifecycle.viewmodel)

    implementation(files("libs/lib-decoder-ffmpeg-release.aar"))
}

tasks.register("checkLocalization") {
    group = "verification"
    description = "Checks flavor string parity and visible hardcoded text."

    doLast {
        val englishStrings = file("src/main/res/values/strings.xml")
        val chineseStrings = file("src/zh/res/values/strings.xml")
        val englishWeb = file("src/en/res/raw/index.html")
        val chineseWeb = file("src/main/res/raw/index.html")
        val han = Regex("[\\u3400-\\u9fff]")

        fun resourceShape(file: File): Map<String, Int> {
            val document = javax.xml.parsers.DocumentBuilderFactory.newInstance()
                .newDocumentBuilder()
                .parse(file)
            val nodes = document.documentElement.childNodes
            return buildMap {
                for (index in 0 until nodes.length) {
                    val node = nodes.item(index)
                    if (node.nodeType != org.w3c.dom.Node.ELEMENT_NODE) continue
                    if (node.nodeName != "string" && node.nodeName != "string-array") continue
                    val name = node.attributes.getNamedItem("name")?.nodeValue ?: continue
                    val itemCount = if (node.nodeName == "string-array") {
                        val children = node.childNodes
                        (0 until children.length).count { children.item(it).nodeName == "item" }
                    } else {
                        1
                    }
                    put(name, itemCount)
                }
            }
        }

        check(resourceShape(englishStrings) == resourceShape(chineseStrings)) {
            "English and Chinese resource names or string-array sizes differ"
        }
        check(!han.containsMatchIn(englishStrings.readText())) {
            "Default English strings contain Chinese text"
        }
        check(englishWeb.isFile && !han.containsMatchIn(englishWeb.readText())) {
            "English web settings page is missing or contains Chinese text"
        }
        check(chineseWeb.isFile && han.containsMatchIn(chineseWeb.readText())) {
            "Chinese web settings page is missing Chinese text"
        }

        val visibleKotlin = listOf(
            Regex("\\.text\\s*=\\s*\"[^\"\\n]*[\\u3400-\\u9fff]"),
            Regex("\\.(?:setText|setTitle|setMessage|setPositiveButton|setNegativeButton)\\s*\\(\\s*\"[^\"\\n]*[\\u3400-\\u9fff]"),
            Regex("\"[^\"\\n]*[\\u3400-\\u9fff][^\"\\n]*\"\\.showToast\\s*\\("),
            Regex("Toast\\.makeText\\([^,\\n]+,\\s*\"[^\"\\n]*[\\u3400-\\u9fff]")
        )
        val kotlinFixtures = listOf(
            "binding.title.text = \"中文\"",
            "dialog.setMessage(\"中文\")",
            "\"中文\".showToast()",
            "Toast.makeText(context, \"中文\", Toast.LENGTH_SHORT)"
        )
        check(visibleKotlin.zip(kotlinFixtures).all { (pattern, fixture) -> pattern.containsMatchIn(fixture) }) {
            "Localization check self-test failed for Kotlin visible text"
        }
        val kotlinViolations = fileTree("src/main/java") { include("**/*.kt") }.files.flatMap { source ->
            source.readLines().mapIndexedNotNull { index, line ->
                if (!line.trimStart().startsWith("//") && visibleKotlin.any { it.containsMatchIn(line) }) {
                    "${source.relativeTo(projectDir)}:${index + 1}"
                } else {
                    null
                }
            }
        }
        check(kotlinViolations.isEmpty()) {
            "Hardcoded visible Chinese text: ${kotlinViolations.joinToString()}"
        }

        val literalVisibleAttribute = Regex("android:(text|contentDescription)\\s*=\\s*\"([^\"]*)\"")
        fun hasHardcodedLayoutText(line: String): Boolean {
            val match = literalVisibleAttribute.find(line) ?: return false
            val attribute = match.groupValues[1]
            val value = match.groupValues[2]
            return value.isNotBlank() && !value.startsWith("@") && !(attribute == "text" && value == "X")
        }
        check(hasHardcodedLayoutText("android:contentDescription=\"Heart Icon\"")) {
            "Localization check self-test failed for layout text"
        }
        val layoutViolations = fileTree("src/main/res/layout") { include("**/*.xml") }.files.flatMap { source ->
            source.readLines().mapIndexedNotNull { index, line ->
                if (hasHardcodedLayoutText(line)) {
                    "${source.relativeTo(projectDir)}:${index + 1}"
                } else {
                    null
                }
            }
        }
        check(layoutViolations.isEmpty()) {
            "Hardcoded layout text: ${layoutViolations.joinToString()}"
        }
    }
}
