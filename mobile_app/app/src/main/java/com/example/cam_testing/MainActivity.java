package com.example.cam_testing;

import android.os.Bundle;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.fragment.app.Fragment;
import com.google.android.material.bottomnavigation.BottomNavigationView;
import android.view.MenuItem;

public class MainActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        BottomNavigationView bottomNavigationView = findViewById(R.id.bottom_navigation);
        bottomNavigationView.setOnItemSelectedListener(navListener);

        // Load HomeFragment by default
        getSupportFragmentManager().beginTransaction().replace(R.id.fragment_container, new HomeActivity()).commit();
    }

    private final BottomNavigationView.OnItemSelectedListener navListener =
            new BottomNavigationView.OnItemSelectedListener() {
                @Override
                public boolean onNavigationItemSelected(@NonNull MenuItem item) {
                    Fragment selectedFragment = null;

                    if (item.getItemId() == R.id.nav_home) {
                        selectedFragment = new HomeActivity();
                    } else if (item.getItemId() == R.id.nav_analytics) {
                        selectedFragment = new AnalyticsFragment();
                    } else if (item.getItemId() == R.id.nav_camera) {
                        selectedFragment = new CameraFragment();
                    } else if (item.getItemId() == R.id.nav_alerts) {
                        selectedFragment = new AlertFragment();
                    }

                    if (selectedFragment != null) {
                        getSupportFragmentManager().beginTransaction().replace(R.id.fragment_container, selectedFragment).commit();
                    }

                    return true;
                }
            };
}
