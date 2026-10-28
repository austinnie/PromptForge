# test_model_routing.py
from core.intent_analyzer import IntentAnalyzer
from core.skill_routes import match_skill

def run_test():
    analyzer = IntentAnalyzer()

    test_cases = [
        # (用户输入, 预期 type, 预期 params/skill 信息)
        ("帮我看看有哪些模型", "skill", "local_model_manage", "list"),
        ("列出所有本地模型", "skill", "local_model_manage", "list"),
        ("切换模型 sd_v1_5_aiiiiii01_v10", "skill", "local_model_manage", "switch"),
        ("换个模型吧，用 ov_int8_sd15", "skill", "local_model_manage", "switch"),
        ("画一只在窗台上的猫", "text_to_image", None, None), # 确保不误伤文生图
    ]

    print("🚀 开始测试意图识别与路由分发...\n" + "="*50)
    
    for text, exp_type, exp_skill, exp_action in test_cases:
        print(f"🗣️ 用户输入: {text}")
        
        # 1. 测试 match_skill 能否命中
        hit = match_skill(text)
        if exp_skill:
            if hit:
                skill_name, kw = hit
                print(f"   [路由命中] -> {skill_name} (关键词: {kw})")
            else:
                print(f"   ❌ [路由失败] 未命中任何技能")
        
        # 2. 测试 IntentAnalyzer 的解析结果
        intent = analyzer.analyze(text)
        print(f"   [意图解析] -> type: {intent.type}, params: {intent.params}")
        
        # 3. 断言验证
        passed = True
        if intent.type != exp_type:
            print(f"   ❌ 断言失败: 期望 type={exp_type}, 实际={intent.type}")
            passed = False
        
        if exp_skill and intent.params.get("skill") != exp_skill:
            print(f"   ❌ 断言失败: 期望 skill={exp_skill}, 实际={intent.params.get('skill')}")
            passed = False
            
        if exp_action and intent.params.get("action") != exp_action:
            print(f"   ❌ 断言失败: 期望 action={exp_action}, 实际={intent.params.get('action')}")
            passed = False

        if passed:
            print("   ✅ 测试通过\n" + "-"*50)
        else:
            print("   ⚠️ 测试失败\n" + "-"*50)

if __name__ == "__main__":
    run_test()