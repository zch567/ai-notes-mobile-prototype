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
        versionCode = 2
        versionName = "0.1.1"
    }
}

val npmCommand = if (System.getProperty("os.name").lowercase().contains("windows")) {
    "npm.cmd"
} else {
    "npm"
}

val frontendRoot = rootProject.file("..")
val webviewDist = frontendRoot.resolve("dist-webview")
val generatedAssetsRoot = layout.buildDirectory.dir("generated/assets").get().asFile
val generatedWebAssets = generatedAssetsRoot.resolve("web")

val buildFrontendWebview by tasks.registering(Exec::class) {
    workingDir = frontendRoot
    commandLine(npmCommand, "run", "build:webview")
    inputs.files(
        frontendRoot.resolve("package.json"),
        frontendRoot.resolve("package-lock.json"),
        frontendRoot.resolve("vite.config.js"),
        frontendRoot.resolve("index.html"),
        frontendRoot.resolve("App.jsx"),
    )
    inputs.dir(frontendRoot.resolve("src"))
    outputs.dir(webviewDist)
}

val syncFrontendWebAssets by tasks.registering(Sync::class) {
    dependsOn(buildFrontendWebview)
    from(webviewDist)
    into(generatedWebAssets)
}

android.sourceSets["main"].assets.srcDir(generatedAssetsRoot)

tasks.configureEach {
    if (name == "mergeDebugAssets" || name == "mergeReleaseAssets") {
        dependsOn(syncFrontendWebAssets)
    }
}
