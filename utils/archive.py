import time
from selenium.webdriver.support.wait import WebDriverWait

maxNum = 20


def get_main_url(driver):
    time.sleep(2)
    url_set = set()
    num = 0
    while True:
        num += 1
        # 使用JavaScript来访问Shadow DOM并找到嵌套的元素
        script = """
        return document.querySelector('body > app-root').shadowRoot
        .querySelector('#maincontent > div > router-slot > home-page').shadowRoot
        .querySelector('#page-content-container > infinite-scroller').shadowRoot
        .querySelector('#container');
        """

        # 执行JavaScript并获取目标元素
        nested_element_container = driver.execute_script(script)

        if nested_element_container:
            # 获取 <collection-tile> 中的 <a> 标签
            collection_tile_script = """
            let collectionTiles = arguments[0].querySelectorAll('collection-tile');
            let links = [];
            collectionTiles.forEach(tile => {
                let shadowRoot = tile.shadowRoot;
                if (shadowRoot) {
                    let link = shadowRoot.querySelector('a');
                    if (link) {
                        links.push(link);
                    }
                }
            });
            return links;
            """
            links = driver.execute_script(collection_tile_script, nested_element_container)

            if links:
                for index, link in enumerate(links):
                    link_href = link.get_attribute('href')
                    url_set.add(link_href)
            else:
                break

            # 滚动到页面底部
            scroll_to_bottom(driver)
            if num == maxNum:
                break
        else:
            break
    return url_set


def get_details_url(driver):
    time.sleep(2)
    url_set = set()
    num = 0
    while True:
        num += 1
        # 使用JavaScript来访问Shadow DOM并找到嵌套的元素
        script = """
        function getNestedElement() {
            try {
                let appRoot = document.querySelector("body > app-root");
                if (!appRoot) {
                    throw new Error("app-root not found");
                }

                let detailsPage = appRoot.shadowRoot.querySelector("#maincontent > div > router-slot > details-page-router > collection-page");
                if (!detailsPage) {
                    throw new Error("collection-page not found");
                }

                let collectionBrowser = detailsPage.shadowRoot.querySelector("#collection-browser-container > collection-browser");
                if (!collectionBrowser) {
                    throw new Error("collection-browser not found");
                }

                let infiniteScroller = collectionBrowser.shadowRoot.querySelector("#right-column > infinite-scroller");
                if (!infiniteScroller) {
                    throw new Error("infinite-scroller not found");
                }

                let container = infiniteScroller.shadowRoot.querySelector("#container");
                if (!container) {
                    throw new Error("container not found");
                }
                return container;
            } catch (error) {
                console.error(error);
                return null;
            }
        }    
        return getNestedElement();
        """

        # 执行JavaScript并获取目标元素
        nested_element_container = driver.execute_script(script)
        if nested_element_container:
            # 获取 <cell-container> 中的 <a> 标签
            cell_container_script = """
            cellContainers = arguments[0].querySelectorAll('article');
            var links = [];
            cellContainers.forEach(tile => {
                tile_dispatcher = tile.querySelector("tile-dispatcher")
                if (tile_dispatcher){
                    container = tile_dispatcher.shadowRoot.querySelector("#container");
                    if (container) {
                        let link = container.querySelector('a');
                        if (link) {
                            links.push(link);
                        }
                    }
                }
            });

            return links;
            """
            links = driver.execute_script(cell_container_script, nested_element_container)
            if links:
                for index, link in enumerate(links):
                    link_href = link.get_attribute('href')
                    url_set.add(link_href)
            else:
                break
        else:
            break

        # 滚动到页面底部
        scroll_to_bottom(driver)
        if num == maxNum:
            break
    return url_set


# 定义一个函数来滚动页面
def scroll_to_bottom(driver, pause_time=2):
    last_height = driver.execute_script("return document.body.scrollHeight")

    # 滚动到页面底部
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    # 使用显式等待等待页面加载新内容
    try:
        WebDriverWait(driver, pause_time).until(
            lambda d: d.execute_script("return document.body.scrollHeight") > last_height
        )
    except:
        return False

    # 计算新的滚动高度并与最后的高度进行比较
    new_height = driver.execute_script("return document.body.scrollHeight")
    if new_height == last_height:
        time.sleep(pause_time)
        new_height = driver.execute_script("return document.body.scrollHeight")
    last_height = new_height
