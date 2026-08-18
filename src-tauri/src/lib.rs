use tauri::{webview::WebviewWindowBuilder, WebviewUrl};
use url::Url;

fn is_packaged_local_url(url: &Url) -> bool {
    if url.port().is_some()
        || !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
        || !matches!(url.path(), "/" | "/index.html")
    {
        return false;
    }

    (url.scheme() == "tauri" && url.host_str() == Some("localhost"))
        || matches!(url.scheme(), "http" | "https") && url.host_str() == Some("tauri.localhost")
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .on_navigation(is_packaged_local_url)
                .on_new_window(|_, _| tauri::webview::NewWindowResponse::Deny)
                .build()?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("failed to run Nana static shell");
}

#[cfg(test)]
mod tests {
    use super::is_packaged_local_url;
    use url::Url;

    #[test]
    fn navigation_boundary_accepts_only_packaged_local_hosts() {
        assert!(is_packaged_local_url(
            &Url::parse("tauri://localhost/index.html").unwrap()
        ));
        assert!(is_packaged_local_url(
            &Url::parse("https://tauri.localhost/index.html").unwrap()
        ));
        assert!(!is_packaged_local_url(
            &Url::parse("http://localhost:5173/index.html").unwrap()
        ));
        assert!(!is_packaged_local_url(
            &Url::parse("http://tauri.localhost:5173/index.html").unwrap()
        ));
        assert!(!is_packaged_local_url(
            &Url::parse("http://tauri.localhost/assets/index.js").unwrap()
        ));
        assert!(!is_packaged_local_url(
            &Url::parse("http://tauri.localhost/index.html?remote=1").unwrap()
        ));
        assert!(!is_packaged_local_url(
            &Url::parse("https://example.com/index.html").unwrap()
        ));
    }
}
