"""
Test script for Enhanced Resume Skill Extractor
Run this to verify all enhanced features are working
"""

from enhanced_skill_extractor import EnhancedSkillExtractor
from resume_parser import ResumeParser


def test_alias_detection():
    """Test if skill aliases are detected correctly"""
    print("=" * 60)
    print("Test 1: Alias Detection")
    print("=" * 60)
    
    extractor = EnhancedSkillExtractor()
    
    test_text = """
    I am proficient in Py, JS, ReactJS, and Golang.
    I also know PostgreSQL and K8s. 
    """
    
    result = extractor.extract_skills(test_text)
    
    print(f"✅ Total skills found: {result['total_count']}")
    print("Skills detected:")
    for skill in result['skills']:
        print(f"  - {skill['name']}")
    
    # Check if aliases were matched to canonical names
    skill_names = [s['name'] for s in result['skills']]
    
    assert 'Python' in skill_names, "❌ 'Py' should match to 'Python'"
    assert 'JavaScript' in skill_names, "❌ 'JS' should match to 'JavaScript'"
    assert 'React' in skill_names, "❌ 'ReactJS' should match to 'React'"
    assert 'Go' in skill_names, "❌ 'Golang' should match to 'Go'"
    assert 'PostgreSQL' in skill_names, "❌ 'PostgreSQL' should be detected"
    assert 'Kubernetes' in skill_names, "❌ 'K8s' should match to 'Kubernetes'"
    
    print("✅ All alias tests passed!")
    return True


def test_role_inference():
    """Test if skills are inferred from job roles"""
    print("\n" + "=" * 60)
    print("Test 2: Role-Based Skill Inference")
    print("=" * 60)
    
    extractor = EnhancedSkillExtractor()
    
    test_text = """
    I worked as a Full Stack Developer for 3 years.
    Previously, I was a Data Scientist at XYZ Corp.
    """
    
    result = extractor.extract_all_skills(test_text)
    
    print(f"✅ Total skills found: {result['total_count']}")
    print(f"   - Explicit: {result['explicit_count']}")
    print(f"   - Inferred: {result['inferred_count']}")
    
    print("\nInferred skills:")
    for skill in result['skills']:
        if skill['source'] == 'inferred':
            print(f"  - {skill['name']} (from {skill.get('from_role', 'unknown')})")
    
    # Check if skills were inferred
    inferred_names = [s['name'] for s in result['skills'] if s['source'] == 'inferred']
    
    assert len(inferred_names) > 0, "❌ Should infer skills from roles"
    assert 'HTML' in inferred_names or 'CSS' in inferred_names, "❌ Should infer web skills from Full Stack Developer"
    
    print("✅ Role inference test passed!")
    return True


def test_skill_level_detection():
    """Test if skill proficiency levels are detected"""
    print("\n" + "=" * 60)
    print("Test 3: Skill Level Detection")
    print("=" * 60)
    
    extractor = EnhancedSkillExtractor()
    
    test_text = """
    I am an expert in Python with 7 years of experience.
    I have intermediate knowledge of Java (3 years).
    I have basic knowledge of Rust.
    """
    
    result = extractor.extract_all_skills(test_text)
    
    print("Skills with levels:")
    for skill_name, level_info in result['skill_levels'].items():
        level = level_info.get('level', 'unknown')
        years = level_info.get('years', '')
        years_str = f"({years} years)" if years else ""
        print(f"  - {skill_name}: {level.upper()} {years_str}")
    
    # Check if levels were detected
    python_level = result['skill_levels'].get('Python', {})
    java_level = result['skill_levels'].get('Java', {})
    rust_level = result['skill_levels'].get('Rust', {})
    
    assert python_level.get('level') == 'expert', "❌ Python should be expert level"
    assert python_level.get('years') == 7, "❌ Python should have 7 years"
    assert java_level.get('level') == 'intermediate', "❌ Java should be intermediate level"
    assert rust_level.get('level') == 'beginner', "❌ Rust should be beginner level"
    
    print("✅ Level detection test passed!")
    return True


def test_complete_extraction():
    """Test complete extraction with sample resume"""
    print("\n" + "=" * 60)
    print("Test 4: Complete Extraction with Sample Resume")
    print("=" * 60)
    
    parser = ResumeParser()
    extractor = EnhancedSkillExtractor()
    
    try:
        # Try to load enhanced sample resume
        text = parser.extract_text('enhanced_sample_resume.txt')
    except:
        # Fallback to inline test
        text = """
        SARAH JOHNSON
        Full Stack Developer
        
        Email: sarah@email.com
        
        Expert in Python (6 years), JavaScript, and React.
        Proficient in AWS and Docker.
        Basic knowledge of Kubernetes.
        
        Senior Full Stack Developer at Tech Corp
        - Built applications with Node.js and PostgreSQL
        """
    
    result = extractor.extract_all_skills(text)
    summary = extractor.get_skills_summary(result)
    
    print(f"✅ Total skills: {summary['total_skills']}")
    print(f"   - Explicit: {summary['explicit_skills']}")
    print(f"   - Inferred: {summary['inferred_skills']}")
    print(f"   - Categories: {summary['categories_found']}")
    
    print(f"\nSkill levels breakdown:")
    for level, count in summary['skills_with_levels'].items():
        print(f"   - {level.title()}: {count}")
    
    print("\nTop 10 skills:")
    for i, skill in enumerate(result['skills'][:10], 1):
        level_info = result['skill_levels'].get(skill['name'], {})
        level = level_info.get('level', 'unknown')
        source = "✅" if skill['source'] == 'explicit' else "🔮"
        print(f"   {i}. {skill['name']} ({skill['category']}) - {level} {source}")
    
    assert result['total_count'] > 0, "❌ Should find at least some skills"
    assert result['explicit_count'] > 0, "❌ Should find explicit skills"
    
    print("✅ Complete extraction test passed!")
    return True


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("ENHANCED SKILL EXTRACTOR - TEST SUITE")
    print("=" * 60 + "\n")
    
    tests = [
        test_alias_detection,
        test_role_inference,
        test_skill_level_detection,
        test_complete_extraction
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            results.append(False)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nYou can now run the enhanced app:")
        print("  streamlit run enhanced_app.py")
        return True
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        failed_count = results.count(False)
        print(f"\nFailed: {failed_count}/{len(results)} tests")
        return False


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)