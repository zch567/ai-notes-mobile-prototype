plugins {
    id("com.android.application")
}

android {
    namespace = "com.zhixu.notesdemo"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.zhixu.notesdemo"
        minSdk = 23
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
    }
}

val npmCommand = if (System.getProperty("os.name").lowercase().contains("windows")) {
    "npm.cmd"
} else {
    "npm"
}

val generatedAssetsRoot = layout.buildDirectory.dir("generated/assets").get().asFile
val generatedWebAssets = generatedAssetsRoot.resolve("web")

val buildFrontendWebview by tasks.registering(Exec::class) {
    workingDir = rootProject.file("..")
    commandLine(npmCommand, "run", "build:webview")
}

val syncFrontendWebAssets by tasks.registering(Sync::class) {
    dependsOn(buildFrontendWebview)
    from(rootProject.file("../dist"))
    into(generatedWebAssets)
}

android.sourceSets["main"].assets.srcDir(generatedAssetsRoot)

tasks.configureEach {
    if (name == "mergeDebugAssets" || name == "mergeReleaseAssets") {
        dependsOn(syncFrontendWebAssets)
    }
}
