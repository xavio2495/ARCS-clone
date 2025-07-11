plugins {
    alias(libs.plugins.android.application)
}


android {
    namespace = "com.example.cam_testing"
    compileSdk = 34 // Keep it at 34 for AGP 8.5.0 compatibility

    defaultConfig {
        applicationId = "com.example.cam_testing"
        minSdk = 21 // Update to 21 to avoid conflicts with ConstraintLayout
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
}

dependencies {
    implementation(libs.appcompat)
    implementation(libs.material) // Ensure this is a version compatible with minSdk 19
    implementation(libs.constraintlayout)

    // Downgrade androidx.activity to 1.9.0 for compatibility with API 34
    implementation("com.squareup.picasso:picasso:2.8")
    implementation("androidx.activity:activity:1.9.0")
    implementation ("androidx.constraintlayout:constraintlayout:1.1.3")
    implementation ("io.socket:socket.io-client:2.0.0")
    testImplementation(libs.junit)
    androidTestImplementation(libs.ext.junit)
    androidTestImplementation(libs.espresso.core)
}
