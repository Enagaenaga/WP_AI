<?php
/**
 * Plugin Name: WP Doctor AI (Diagnostics API)
 * Description: 提供仕様に基づく診断用REST APIエンドポイント
 * Version: 0.1.0
 */

if (!defined('ABSPATH')) { exit; }

add_action('rest_api_init', function () {
    $ns = 'wpdoctor/v1';

    register_rest_route($ns, '/system-info', [
        'methods' => 'GET',
        'callback' => function (WP_REST_Request $req) {
            return new WP_REST_Response([
                'wordpress_version' => get_bloginfo('version'),
                'php_version' => phpversion(),
                'server_os' => PHP_OS_FAMILY,
            ], 200);
        },
        'permission_callback' => 'wpdoctor_api_require_basic_auth',
    ]);

    register_rest_route($ns, '/plugins-analysis', [
        'methods' => 'GET',
        'callback' => function (WP_REST_Request $req) {
            if (!function_exists('get_plugins')) { require_once ABSPATH . 'wp-admin/includes/plugin.php'; }
            $status = $req->get_param('status') ?: 'active';
            $plugins = get_plugins();
            $active = get_option('active_plugins', []);
            $list = [];
            $updates = [];
            foreach ($plugins as $file => $data) {
                $is_active = in_array($file, $active, true);
                if ($status === 'active' && !$is_active) continue;
                $list[] = [
                    'file' => $file,
                    'name' => $data['Name'] ?? '',
                    'version' => $data['Version'] ?? '',
                    'status' => $is_active ? 'active' : 'inactive',
                ];
            }
            if (function_exists('get_plugin_updates')) {
                $upd = get_plugin_updates();
                foreach ($upd as $file => $info) {
                    $updates[] = [
                        'file' => $file,
                        'new_version' => $info->update->new_version ?? null,
                    ];
                }
            }
            return new WP_REST_Response([
                'plugins' => $list,
                'active_count' => count(array_filter($list, fn($p) => $p['status'] === 'active')),
                'updates' => $updates,
            ], 200);
        },
        'permission_callback' => 'wpdoctor_api_require_basic_auth',
    ]);

    register_rest_route($ns, '/error-logs', [
        'methods' => 'GET',
        'callback' => function (WP_REST_Request $req) {
            $lines = intval($req->get_param('lines') ?: 50);
            $level = $req->get_param('level') ?: 'all';
            $paths = [
                WP_CONTENT_DIR . '/debug.log',
                ABSPATH . 'error_log',
            ];
            $tail = [];
            foreach ($paths as $p) {
                if (file_exists($p)) {
                    $content = @file($p);
                    if (is_array($content)) {
                        $tail = array_slice(array_map('rtrim', $content), -$lines);
                        break;
                    }
                }
            }
            return new WP_REST_Response([
                'tail' => $tail,
                'source' => $p ?? null,
            ], 200);
        },
        'permission_callback' => 'wpdoctor_api_require_basic_auth',
    ]);

    register_rest_route($ns, '/db-check', [
        'methods' => 'GET',
        'callback' => function (WP_REST_Request $req) {
            global $wpdb;
            $autoload_bytes = intval($wpdb->get_var("SELECT SUM(LENGTH(option_value)) FROM {$wpdb->options} WHERE autoload='yes'"));
            $overhead = $wpdb->get_results('SHOW TABLE STATUS', ARRAY_A);
            $overhead_sum = 0;
            foreach ($overhead as $row) { $overhead_sum += intval($row['Data_free'] ?? 0); }
            return new WP_REST_Response([
                'autoload_size' => $autoload_bytes,
                'overhead' => $overhead_sum,
            ], 200);
        },
        'permission_callback' => 'wpdoctor_api_require_basic_auth',
    ]);
});

function wpdoctor_api_require_basic_auth() {
    // Application Passwords を利用する想定。権限は管理者のみ。
    return current_user_can('manage_options');
}
