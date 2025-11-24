<?php
/**
 * Plugin Name: WP Doctor AI (Diagnostics API)
 * Description: 提供仕様に基づく診断用REST APIエンドポイント
 * Version: 0.1.0
 */

if (!defined('ABSPATH')) { exit; }

add_action('rest_api_init', function () {
    $ns = 'wpdoctor/v1';

    // Quick checks
    register_rest_route($ns, '/quick-checks', [
        'methods' => 'GET',
        'callback' => function (WP_REST_Request $req) {
            global $wpdb;
            $https = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') || (isset($_SERVER['SERVER_PORT']) && $_SERVER['SERVER_PORT'] == 443);
            $mem = ini_get('memory_limit');
            $max_exec = ini_get('max_execution_time');
            $db_ver = $wpdb->db_version();
            $debug = defined('WP_DEBUG') ? (WP_DEBUG ? 'on' : 'off') : 'unknown';
            $extensions = [
                'json' => extension_loaded('json'),
                'curl' => extension_loaded('curl'),
                'mbstring' => extension_loaded('mbstring'),
                'openssl' => extension_loaded('openssl'),
            ];
            $fs_write = is_writable(WP_CONTENT_DIR);
            return new WP_REST_Response([
                'https' => $https,
                'memory_limit' => $mem,
                'max_execution_time' => $max_exec,
                'wp_version' => get_bloginfo('version'),
                'db_version' => $db_ver,
                'debug' => $debug,
                'extensions' => $extensions,
                'file_system' => [ 'wp_content_writable' => $fs_write ],
            ], 200);
        },
        'permission_callback' => 'wpdoctor_api_require_basic_auth',
    ]);

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
            $with_updates = filter_var($req->get_param('with_updates'), FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE);
            if ($with_updates === null) { $with_updates = true; }

            $plugins = get_plugins();
            $active = get_option('active_plugins', []);
            $list = [];

            $updates = [];
            if ($with_updates && function_exists('get_plugin_updates')) {
                $u = get_plugin_updates();
                foreach ($u as $f => $info) {
                    $updates[$f] = $info->update->new_version ?? null;
                }
            }

            foreach ($plugins as $file => $data) {
                $is_active = in_array($file, $active, true);
                if ($status === 'active' && !$is_active) continue;
                if ($status === 'inactive' && $is_active) continue;

                $name = $data['Name'] ?? '';
                $desc = $data['Description'] ?? '';
                $cat = 'other';
                $text = strtolower($name . ' ' . $desc);
                if (str_contains($text, 'seo')) $cat = 'seo';
                elseif (str_contains($text, 'cache')) $cat = 'cache';
                elseif (str_contains($text, 'security') || str_contains($text, 'firewall')) $cat = 'security';
                elseif (str_contains($text, 'backup')) $cat = 'backup';

                $new_ver = $updates[$file] ?? null;
                $list[] = [
                    'file' => $file,
                    'name' => $name,
                    'version' => $data['Version'] ?? '',
                    'status' => $is_active ? 'active' : 'inactive',
                    'category' => $cat,
                    'has_update' => $new_ver ? true : false,
                    'new_version' => $new_ver,
                ];
            }
            return new WP_REST_Response([
                'plugins' => $list,
                'active_count' => count(array_filter($list, fn($p) => $p['status'] === 'active')),
            ], 200);
        },
        'permission_callback' => 'wpdoctor_api_require_basic_auth',
    ]);

    register_rest_route($ns, '/error-logs', [
        'methods' => 'GET',
        'callback' => function (WP_REST_Request $req) {
            $lines = intval($req->get_param('lines') ?: 50);
            $level = strtolower($req->get_param('level') ?: 'all');
            $format = strtolower($req->get_param('format') ?: 'json');
            $source = strtolower($req->get_param('source') ?: 'auto');
            $since = $req->get_param('since'); // e.g., '1h', '24h', ISO8601

            $paths = [];
            if ($source === 'wp_debug' || $source === 'auto') { $paths[] = WP_CONTENT_DIR . '/debug.log'; }
            if ($source === 'php_error' || $source === 'auto') { $paths[] = ABSPATH . 'error_log'; }
            if (empty($paths)) { $paths = [WP_CONTENT_DIR . '/debug.log', ABSPATH . 'error_log']; }

            $picked = null; $tail = [];
            foreach ($paths as $p) {
                if (file_exists($p)) {
                    $content = @file($p);
                    if (is_array($content)) {
                        $lines_arr = array_map('rtrim', $content);
                        // since フィルタ（簡易）
                        if ($since) {
                            $cut_ts = null;
                            if (preg_match('/^(\d+)([smhd])$/', $since, $m)) {
                                $mult = ['s'=>1,'m'=>60,'h'=>3600,'d'=>86400][$m[2]]; $cut_ts = time() - (intval($m[1]) * $mult);
                            } else {
                                $t = strtotime($since); if ($t !== false) { $cut_ts = $t; }
                            }
                            if ($cut_ts) {
                                $lines_arr = array_values(array_filter($lines_arr, function($ln) use ($cut_ts) {
                                    // ざっくり日時抽出（YYYY-MM-DD or DD-Mon-YYYY など）
                                    if (preg_match('/(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})/', $ln, $mm)) {
                                        $ts = strtotime($mm[1]); return $ts && $ts >= $cut_ts;
                                    }
                                    return true; // 形式不明なら残す
                                }));
                            }
                        }
                        // level フィルタ（簡易）
                        if ($level !== 'all') {
                            $re = match($level) {
                                'error' => '/error/i',
                                'warning' => '/warn/i',
                                'notice' => '/notice/i',
                                default => null,
                            };
                            if ($re) {
                                $lines_arr = array_values(array_filter($lines_arr, fn($ln) => preg_match($re, $ln)));
                            }
                        }
                        $picked = $p;
                        $tail = array_slice($lines_arr, -$lines);
                        break;
                    }
                }
            }
            if ($format === 'raw') {
                $resp = new WP_REST_Response(implode("\n", $tail), 200);
                $resp->header('Content-Type', 'text/plain; charset=UTF-8');
                return $resp;
            }
            return new WP_REST_Response([
                'tail' => $tail,
                'count' => count($tail),
                'source' => $picked,
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

    // Actions (expanded)
    register_rest_route($ns, '/actions', [
        'methods' => 'POST',
        'callback' => function (WP_REST_Request $req) {
            $p = $req->get_json_params();
            $action = $p['action'] ?? '';
            $meta = [];
            switch ($action) {
                case 'rewrite_flush':
                    $hard = !empty($p['hard']);
                    flush_rewrite_rules($hard);
                    $meta['hard'] = $hard;
                    $ok = true;
                    break;
                case 'cache_flush':
                    if (function_exists('wp_cache_flush')) { wp_cache_flush(); }
                    $ok = true;
                    break;
                case 'transients_flush':
                    global $wpdb;
                    $wpdb->query("DELETE FROM {$wpdb->options} WHERE option_name LIKE '\_transient\_%' OR option_name LIKE '\_site\_transient\_%'");
                    $ok = true;
                    break;
                case 'plugin_toggle':
                    if (!function_exists('activate_plugin')) { require_once ABSPATH . 'wp-admin/includes/plugin.php'; }
                    $plugin = $p['plugin'] ?? '';
                    $enable = !empty($p['enable']);
                    if (!$plugin) { return new WP_REST_Response(['error' => 'plugin required'], 400); }
                    if ($enable) {
                        $e = activate_plugin($plugin, '', false, false);
                        if (is_wp_error($e)) { return new WP_REST_Response(['error' => $e->get_error_message()], 400); }
                    } else {
                        deactivate_plugins([$plugin], false, false);
                    }
                    $ok = true;
                    $meta = ['plugin' => $plugin, 'enable' => $enable];
                    break;
                default:
                    return new WP_REST_Response(['error' => 'unknown action'], 400);
            }
            return new WP_REST_Response(['ok' => $ok, 'action' => $action, 'meta' => $meta], 200);
        },
        'permission_callback' => 'wpdoctor_api_require_basic_auth',
        'args' => [
            'action' => [ 'required' => true ],
        ],
    ]);

    // LLM config
    register_rest_route($ns, '/llm-config', [
        'methods' => WP_REST_Server::READABLE,
        'callback' => function (WP_REST_Request $req) {
            $cfg = get_option('wpdoctorai_llm') ?: [];
            if (isset($cfg['api_key'])) { $cfg['api_key'] = '***'; }
            return new WP_REST_Response($cfg, 200);
        },
        'permission_callback' => 'wpdoctor_api_require_basic_auth',
    ]);
    register_rest_route($ns, '/llm-config', [
        'methods' => WP_REST_Server::CREATABLE,
        'callback' => function (WP_REST_Request $req) {
            $p = $req->get_json_params() ?: [];
            $provider = strtolower($p['provider'] ?? '');
            $base_url = $p['base_url'] ?? '';
            $model = $p['model'] ?? '';
            $api_key = $p['api_key'] ?? '';
            $errors = [];
            if ($provider && !in_array($provider, ['gemini','openai'])) { $errors[] = 'provider must be gemini or openai'; }
            if ($base_url && !preg_match('#^https?://#', $base_url)) { $errors[] = 'base_url must be http(s) URL'; }
            if (!$model) { $errors[] = 'model required'; }
            if ($api_key && strlen($api_key) < 8) { $errors[] = 'api_key too short'; }
            if ($errors) { return new WP_REST_Response(['errors' => $errors], 400); }
            $cfg = array_filter([
                'provider' => $provider ?: null,
                'base_url' => $base_url ?: null,
                'model' => $model ?: null,
                'api_key' => $api_key ?: null,
            ]);
            update_option('wpdoctorai_llm', $cfg, false);
            $out = $cfg; if (isset($out['api_key'])) { $out['api_key'] = '***'; }
            return new WP_REST_Response($out, 200);
        },
        'permission_callback' => 'wpdoctor_api_require_basic_auth',
    ]);

    // LLM chat (dummy)
    register_rest_route($ns, '/llm-chat', [
        'methods' => 'POST',
        'callback' => function (WP_REST_Request $req) {
            $p = $req->get_json_params() ?: [];
            $messages = $p['messages'] ?? [];
            $last = is_array($messages) ? end($messages) : null;
            $content = is_array($last) ? ($last['content'] ?? '') : '';
            return new WP_REST_Response(['content' => "(dummy) 応答: " . mb_substr($content, 0, 200)], 200);
        },
        'permission_callback' => 'wpdoctor_api_require_basic_auth',
    ]);
});

function wpdoctor_api_require_basic_auth() {
    // Application Passwords を利用する想定。権限は管理者のみ。
    return current_user_can('manage_options');
}
